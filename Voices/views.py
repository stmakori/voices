from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.apps import apps
from django.conf import settings
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.db.models import Avg, Count, F, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.contrib.auth.models import User, Permission
from django.core.paginator import Paginator
import csv
from datetime import date as dt_date
from datetime import timedelta
import socket
import urllib.request
import urllib.error
import json
import functools
import time
import base64
from django.core.cache import cache

from .models import (
    Resource, GBVReport, GBVReportStatusUpdate,
    AuditLog, SupportFeedback,
    Article, Blog, Story, Idea, Contact, Team, UserProfile,
)
from .forms import (
    GBVReportForm, SupportFeedbackForm, ContactForm, ProfileUpdateForm,
    PasswordChangeForm, ArticleSubmissionForm, BlogSubmissionForm, StorySubmissionForm,
    ResourceSubmissionForm, IdeaSubmissionForm,
)
from .cognito_service import CognitoService
from .forms import name_validator, phone_validator


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _current_user_role(request):
    if not request.user.is_authenticated:
        return "guest"

    role = request.session.get("user_type")
    if role in {"victim", "contributor"}:
        return role

    profile = _get_or_create_profile(request.user)
    request.session["user_type"] = profile.user_type
    return profile.user_type


def _token_needs_refresh(access_token: str) -> bool:
    """Decode the JWT exp claim (without signature verification) to check expiry.
    Returns True if the token has expired or will expire within 60 seconds."""
    try:
        payload_b64 = access_token.split('.')[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return time.time() >= (payload.get('exp', 0) - 60)
    except Exception:
        return True  # assume refresh needed if decode fails


def _ensure_fresh_token(request) -> str | None:
    """Return a valid Cognito access token, refreshing silently if it is expired.
    Returns None if no token is present in the session or refresh fails (tokens cleared)."""
    access_token = request.session.get('access_token')
    if not access_token:
        return None

    if not _token_needs_refresh(access_token):
        return access_token  # still valid

    refresh_token = request.session.get('refresh_token')
    if not refresh_token:
        return None

    result = CognitoService().refresh_tokens(request.user.username, refresh_token)
    if result['success']:
        request.session['access_token'] = result['access_token']
        if result.get('id_token'):
            request.session['id_token'] = result['id_token']
        return result['access_token']

    # Refresh failed — purge stale tokens so the UI prompts re-login
    for key in ('access_token', 'id_token', 'refresh_token'):
        request.session.pop(key, None)
    return None


def rate_limit(max_attempts: int = 5, window_seconds: int = 300):
    """Decorator: simple IP-based POST rate limiter backed by Django cache.
    GET requests pass through without counting."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.method == 'POST':
                ip = _client_ip(request)
                cache_key = f"rl:{view_func.__name__}:{ip}"
                attempts = cache.get(cache_key, 0)
                if attempts >= max_attempts:
                    messages.error(
                        request,
                        "Too many attempts. Please wait a few minutes before trying again.",
                    )
                    return redirect(request.path)
                cache.set(cache_key, attempts + 1, window_seconds)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def audit_event(request, action, target_type="", target_id="", metadata=None):
    AuditLog.objects.create(
        action=action,
        actor=request.user if request.user.is_authenticated else None,
        target_type=target_type,
        target_id=str(target_id or ""),
        ip_address=_client_ip(request),
        metadata=metadata or {},
    )


def _get_or_create_user_case_insensitive(username, **defaults):
    user = User.objects.filter(username__iexact=username).first()
    if user:
        return user, False
    return User.objects.get_or_create(username=username, defaults=defaults)


# ─────────────────────────────────────────────────────────────────────────────
# GENERAL VIEWS
# ─────────────────────────────────────────────────────────────────────────────

def base(request):
    return render(request, 'base.html', {})


def home(request):
    articles = Article.objects.filter(published=True)[:3]
    return render(request, "home.html", {'articles': articles})


def report_gbv(request):
    if request.user.is_authenticated and _current_user_role(request) == "contributor":
        messages.error(request, "Contributors cannot access the report form. Switch to Reporter to share a report.")
        return redirect('home')

    if request.method == 'POST':
        form = GBVReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            if request.user.is_authenticated:
                report.submitted_by = request.user
            report.save()
            report.set_status(GBVReport.STATUS_RECEIVED, note="Report submitted")
            audit_event(request, "report_submitted", "GBVReport", report.id)
            messages.success(request, 'Your report has been submitted. We will reach out if needed.')
            return redirect('report_gbv')
        else:
            messages.error(request, 'Please review the highlighted fields and try again.')
    else:
        form = GBVReportForm()
    kenya_counties = [
        "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu",
        "Garissa", "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho",
        "Kiambu", "Kilifi", "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale",
        "Laikipia", "Lamu", "Machakos", "Makueni", "Mandera", "Marsabit",
        "Meru", "Migori", "Mombasa", "Murang'a", "Nairobi", "Nakuru", "Nandi",
        "Narok", "Nyamira", "Nyandarua", "Nyeri", "Samburu", "Siaya",
        "Taita-Taveta", "Tana River", "Tharaka-Nithi", "Trans Nzoia", "Turkana",
        "Uasin Gishu", "Vihiga", "Wajir", "West Pokot",
    ]
    return render(request, "report-gbv.html", {'form': form, 'kenya_counties': kenya_counties})


@login_required
def report_timeline(request, report_id):
    if request.user.is_staff:
        report = get_object_or_404(GBVReport, id=report_id)
    else:
        report = get_object_or_404(GBVReport, id=report_id, submitted_by=request.user)
    updates = report.status_updates.all()

    elapsed = timezone.now() - report.status_updated_at
    elapsed_hours = max(int(elapsed.total_seconds() // 3600), 0)
    elapsed_days = elapsed_hours // 24

    eta_hours_by_status = {
        GBVReport.STATUS_RECEIVED: 24,
        GBVReport.STATUS_ASSIGNED: 72,
        GBVReport.STATUS_IN_PROGRESS: 168,
    }
    status_next_step = {
        GBVReport.STATUS_RECEIVED: "Case review and assignment",
        GBVReport.STATUS_ASSIGNED: "Case worker engagement",
        GBVReport.STATUS_IN_PROGRESS: "Resolution and closure update",
        GBVReport.STATUS_CLOSED: "Case closed",
    }

    target_hours = eta_hours_by_status.get(report.status)
    if report.status == GBVReport.STATUS_CLOSED:
        eta_text = "This report has been closed."
    elif target_hours is None:
        eta_text = "Next update will be shared as soon as it is available."
    else:
        remaining = target_hours - elapsed_hours
        if remaining > 0:
            eta_text = f"Estimated next update within {remaining} hour(s)."
        else:
            eta_text = f"Status update is overdue by {abs(remaining)} hour(s)."

    status_insight = {
        "elapsed_hours": elapsed_hours,
        "elapsed_days": elapsed_days,
        "next_step": status_next_step.get(report.status, "Next update"),
        "eta_text": eta_text,
    }

    feedbacks = report.feedback_items.order_by("created_at")

    return render(
        request,
        "report_timeline.html",
        {"report": report, "updates": updates, "status_insight": status_insight, "feedbacks": feedbacks},
    )


def education(request):
    category_filter = request.GET.get('category', '')
    type_filter = request.GET.get('type', 'all')
    page_number = request.GET.get('page', 1)

    articles_qs = Article.objects.filter(published=True).order_by('-created_at')
    blogs_qs = Blog.objects.filter(published=True).order_by('-created_at')
    community_stories = []
    include_stories = type_filter in {'all', 'stories'}

    if type_filter == 'blogs':
        articles_qs = Article.objects.none()
    elif type_filter == 'articles':
        blogs_qs = Blog.objects.none()
    elif type_filter == 'stories':
        articles_qs = Article.objects.none()
        blogs_qs = Blog.objects.none()

    if category_filter:
        if type_filter != 'blogs':
            articles_qs = articles_qs.filter(category=category_filter)
        if type_filter != 'articles':
            blogs_qs = blogs_qs.filter(category=category_filter)

    article_paginator = Paginator(articles_qs, 12)
    blog_paginator = Paginator(blogs_qs, 12)
    articles = article_paginator.get_page(page_number)
    blogs = blog_paginator.get_page(page_number)

    has_previous = articles.has_previous() or blogs.has_previous()
    has_next = articles.has_next() or blogs.has_next()
    prev_page = articles.previous_page_number() if articles.has_previous() else (blogs.previous_page_number() if blogs.has_previous() else None)
    next_page = articles.next_page_number() if articles.has_next() else (blogs.next_page_number() if blogs.has_next() else None)
    total_pages = max(article_paginator.num_pages, blog_paginator.num_pages)
    current_page = articles.number if article_paginator.num_pages >= blog_paginator.num_pages else blogs.number

    all_articles = Article.objects.filter(published=True)
    all_blogs = Blog.objects.filter(published=True)
    category_counts = {
        'education':  all_articles.filter(category='education').count() + all_blogs.filter(category='education').count(),
        'prevention': all_articles.filter(category='prevention').count() + all_blogs.filter(category='prevention').count(),
        'support':    all_articles.filter(category='support').count() + all_blogs.filter(category='support').count(),
        'legal':      all_articles.filter(category='legal').count() + all_blogs.filter(category='legal').count(),
        'awareness':  all_articles.filter(category='awareness').count() + all_blogs.filter(category='awareness').count(),
        'recovery':   all_articles.filter(category='recovery').count() + all_blogs.filter(category='recovery').count(),
        'other':      all_articles.filter(category='other').count() + all_blogs.filter(category='other').count(),
    }

    if include_stories:
        for story in Story.objects.filter(published=True).order_by('-created_at'):
            story_text = (story.story or '').strip()
            author_display = story.user.username if story.user else 'Anonymous'
            community_stories.append({
                'title': f"Story by {author_display}",
                'summary': ' '.join(story_text.split()[:24]) + ('...' if len(story_text.split()) > 24 else ''),
                'content': story.story,
                'language': 'en',
                'created_at': story.created_at,
                'author_name': author_display,
                'source_type': 'Community Story',
            })

        community_stories.sort(key=lambda item: item['created_at'], reverse=True)

    context = {
        'articles':        articles,
        'blogs':           blogs,
        'category_counts': category_counts,
        'current_category': category_filter,
        'current_type':    type_filter,
        'stories':         community_stories,
        'page_number':      page_number,
        'has_previous':     has_previous,
        'has_next':         has_next,
        'prev_page':        prev_page,
        'next_page':        next_page,
        'total_pages':      total_pages,
        'current_page':     current_page,
    }
    return render(request, "education.html", context)


def resources(request):
    location_term = request.GET.get('location', '').strip()
    active_type = request.GET.get('resource_type', '').strip()

    qs = Resource.objects.all().order_by('-is_verified', 'name')
    if location_term:
        qs = qs.filter(
            Q(location__icontains=location_term)
            | Q(name__icontains=location_term)
            | Q(address__icontains=location_term)
            | Q(description__icontains=location_term)
        )

    # Pass all location-matched resources; type filtering is done client-side with gray-out
    visible_resources = list(qs)

    context = {
        "resources": visible_resources,
        "active_type": active_type,
        "all_resources_count": Resource.objects.count(),
    }
    return render(request, "resources.html", context)


def _resource_score(resource, incident_type=None):
    score = 0
    if resource.is_verified:
        score += 20
    if resource.open_now is True:
        score += 15
    if incident_type and resource.resource_type == incident_type:
        score += 30
    return score


def _resource_default_county() -> str:
    return getattr(settings, "RESOURCE_DEFAULT_COUNTY", "Nakuru County")


def _default_county_fallback_coords(default_county: str):
    county = (default_county or "").strip().lower()
    if "nakuru" in county:
        return {"lat": -0.3031, "lon": 36.0800}
    return None


def resource_navigate(request, resource_id=None, id=None):
    selected_id = resource_id or id
    resource = get_object_or_404(Resource, id=selected_id) if selected_id else None
    default_county = _resource_default_county()

    if resource and (resource.latitude is None or resource.longitude is None):
        resource._geocode(default_county=default_county)
        if resource.latitude is not None and resource.longitude is not None:
            resource.save(update_fields=["latitude", "longitude"])

    incident_type = request.GET.get("incident_type")
    all_resources = list(Resource.objects.all())
    all_resources.sort(key=lambda r: _resource_score(r, incident_type), reverse=True)

    destination_query_parts = [resource.name if resource else None, resource.location if resource else None, resource.address if resource else None]
    destination_query = ', '.join([p for p in destination_query_parts if p])
    if destination_query and " county" not in destination_query.lower():
        destination_query = f"{destination_query}, {default_county}"
    if destination_query and "kenya" not in destination_query.lower():
        destination_query = f"{destination_query}, Kenya"

    return render(request, "resource_navigate.html", {
        "resource": resource,
        "resources": all_resources,
        "destination_query": destination_query,
        "destination_latitude": resource.latitude if resource else None,
        "destination_longitude": resource.longitude if resource else None,
        "default_county": default_county,
        "default_county_latitude": (_default_county_fallback_coords(default_county) or {}).get("lat"),
        "default_county_longitude": (_default_county_fallback_coords(default_county) or {}).get("lon"),
    })


def resources_map(request):
    qs = Resource.objects.all().order_by('name')
    default_county = _resource_default_county()
    resources_data = []
    for resource in qs:
        if resource.latitude is None or resource.longitude is None:
            resource._geocode(default_county=default_county)
            if resource.latitude is not None and resource.longitude is not None:
                resource.save(update_fields=["latitude", "longitude"])

        resources_data.append({
            "id": resource.id,
            "name": resource.name,
            "resource_type": resource.resource_type,
            "resource_type_label": resource.get_resource_type_display(),
            "location": resource.location,
            "address": resource.address,
            "phone": resource.phone,
            "navigate_url": reverse("resource_navigate", args=[resource.id]),
            "latitude": resource.latitude,
            "longitude": resource.longitude,
        })
    return render(request, "resources-map.html", {
        "resources": qs,
        "resources_count": qs.count(),
        "resources_data": resources_data,
    })


@login_required
def support_feedback(request, report_id):
    if request.user.is_staff:
        report = get_object_or_404(GBVReport, id=report_id)
    else:
        report = get_object_or_404(GBVReport, id=report_id, submitted_by=request.user)
    if request.method == "POST":
        form = SupportFeedbackForm(request.POST)
        if form.is_valid():
            fb = form.save(commit=False)
            fb.report = report
            fb.save()
            audit_event(
                request, "support_feedback_submitted",
                "GBVReport", report.id, {"score": fb.score}
            )
            return redirect("report_timeline", report_id=report.id)
    else:
        form = SupportFeedbackForm()
    return render(request, "support_feedback.html", {"form": form, "report": report})


def about(request):
    team_members = Team.objects.all()
    for index, member in enumerate(team_members):
        member.delay = (index + 2) * 100
    return render(request, "about.html", {
        'team_members': team_members,
        'MEDIA_URL': settings.MEDIA_URL,
    })


def privacy_policy(request):
    return render(request, "privacy_policy.html")


def terms_of_service(request):
    return render(request, "terms_of_service.html")


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST, user=request.user)
        if form.is_valid():
            contact_obj = form.save(commit=False)
            if request.user.is_authenticated:
                contact_obj.user = request.user
            contact_obj.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Your message has been sent successfully.'})
            messages.success(request, "Your message has been sent. We'll get back to you soon.")
            return redirect('contact')
    else:
        form = ContactForm(user=request.user)
    return render(request, "contact.html", {'form': form})


def blog_details(request, id):
    blog = get_object_or_404(Blog, id=id, published=True)
    Blog.objects.filter(id=blog.id).update(views=F('views') + 1)
    blog.refresh_from_db(fields=['views'])
    blogs_list = list(Blog.objects.filter(published=True).order_by('created_at'))
    current_index = next((i for i, b in enumerate(blogs_list) if b.id == blog.id), None)
    previous_blog = blogs_list[current_index - 1] if current_index and current_index > 0 else None
    next_blog = blogs_list[current_index + 1] if current_index is not None and current_index < len(blogs_list) - 1 else None
    related_blogs = Blog.objects.filter(published=True).exclude(id=id)[:3]
    return render(request, "blog-details.html", {
        'blog': blog,
        'related_blogs': related_blogs,
        'previous_blog': previous_blog,
        'next_blog': next_blog,
    })


def article_detail(request, id):
    article = get_object_or_404(Article, id=id, published=True)
    Article.objects.filter(id=article.id).update(views=F('views') + 1)
    article.refresh_from_db(fields=['views'])
    articles_list = list(Article.objects.filter(published=True).order_by('created_at'))
    current_index = next((i for i, a in enumerate(articles_list) if a.id == article.id), None)
    previous_article = articles_list[current_index - 1] if current_index and current_index > 0 else None
    next_article = articles_list[current_index + 1] if current_index is not None and current_index < len(articles_list) - 1 else None
    related_articles = Article.objects.filter(category=article.category, published=True).exclude(id=id)[:3]
    return render(request, "article-details.html", {
        'article': article,
        'articles': related_articles,
        'previous_article': previous_article,
        'next_article': next_article,
    })


def emergency(request):
    return render(request, "emergency.html", {})


@login_required
def ai_chat(request):
    Thread = apps.get_model("django_ai_assistant", "Thread")
    threads = list(
        Thread.objects.filter(
            created_by=request.user,
            assistant_id="gbv_support_assistant",
        ).order_by("-id")[:30]
    )
    thread_data = [
        {"id": t.id, "name": t.name or f"Chat {t.id}", "created_at": t.created_at.isoformat()}
        for t in threads
    ]
    return render(request, "ai_chat.html", {
        "assistant_id": "gbv_support_assistant",
        "threads_json": json.dumps(thread_data),
    })


@login_required
def ai_chat_delete_thread(request, thread_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed."}, status=405)
    Thread = apps.get_model("django_ai_assistant", "Thread")
    thread = get_object_or_404(Thread, id=thread_id, created_by=request.user)
    Message = apps.get_model("django_ai_assistant", "Message")
    message_count = Message.objects.filter(thread=thread).count()
    audit_event(
        request, "ai_chat_deleted", "Thread", thread_id,
        {"message_count": message_count},
    )
    thread.delete()
    return JsonResponse({"success": True})


def contribute(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please sign in as a contributor to access the contribute page.')
        return redirect('login')

    if not request.user.is_staff and not request.user.is_superuser and _current_user_role(request) != "contributor":
        messages.error(request, 'Only contributors can access the contribute page. Switch your role from the profile menu to contribute.')
        return redirect('home')

    return render(request, "contribute_landing.html")


def _contributor_only_redirect(request):
    if not request.user.is_authenticated:
        messages.info(request, 'Please sign in as a contributor to access this page.')
        return redirect('login')

    if request.user.is_staff or request.user.is_superuser:
        return None

    if _current_user_role(request) != "contributor":
        messages.error(request, 'Only contributors can access this page. Switch your role from the profile menu to continue.')
        return redirect('home')

    return None


def _render_contribution_form_page(request, *, form, title, heading, description, button_text, extra_context=None):
    context = {
        'form': form,
        'page_title': title,
        'heading': heading,
        'description': description,
        'button_text': button_text,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, "contribute_form.html", context)


def contribute_article(request):
    gate = _contributor_only_redirect(request)
    if gate:
        return gate

    form = ArticleSubmissionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            article = form.save(commit=False)
            article.published = False
            article.author_user = request.user
            if not article.author:
                article.author = request.user.get_full_name() or request.user.username
            article.save()
            messages.success(request, 'Article submitted. It is now pending review.')
            return redirect('contribute_article')
        messages.error(request, 'Please review the highlighted fields and try again.')

    return _render_contribution_form_page(
        request,
        form=form,
        title='Contribute Article - Voices Against Violence',
        heading='Submit Your Article',
        description='Share educational content on prevention, support, legal rights, and awareness.',
        button_text='Submit Article',
    )


def contribute_blog(request):
    gate = _contributor_only_redirect(request)
    if gate:
        return gate

    form = BlogSubmissionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            blog = form.save(commit=False)
            blog.published = False
            blog.author_user = request.user
            if not blog.author:
                blog.author = request.user.get_full_name() or request.user.username
            blog.save()
            messages.success(request, 'Blog submitted. It is now pending review.')
            return redirect('contribute_blog')
        messages.error(request, 'Please review the highlighted fields and try again.')

    return _render_contribution_form_page(
        request,
        form=form,
        title='Contribute Blog - Voices Against Violence',
        heading='Submit Your Blog Post',
        description='Share practical updates, reflections, and awareness content in blog format.',
        button_text='Submit Blog',
    )


def contribute_story(request):
    gate = _contributor_only_redirect(request)
    if gate:
        return gate

    form = StorySubmissionForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            story = form.save(commit=False)
            story.published = False
            story.save()
            messages.success(request, 'Story submitted. It is now pending review.')
            return redirect('contribute_story')
        messages.error(request, 'Please review the highlighted fields and try again.')

    return _render_contribution_form_page(
        request,
        form=form,
        title='Share Story - Voices Against Violence',
        heading='Share Your Story',
        description='Your story can inspire, support, and help others. You may share anonymously.',
        button_text='Submit Story',
    )


def contribute_resource(request):
    gate = _contributor_only_redirect(request)
    if gate:
        return gate

    default_county = _resource_default_county()
    form = ResourceSubmissionForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            resource = form.save(commit=False)
            resource.is_verified = False
            if resource.latitude is None or resource.longitude is None:
                resource._geocode(default_county=default_county)
            resource.save()
            messages.success(request, 'Resource submitted. It is now pending verification.')
            return redirect('contribute_resource')
        messages.error(request, 'Please review the highlighted fields and try again.')

    return _render_contribution_form_page(
        request,
        form=form,
        title='Add Resource - Voices Against Violence',
        heading='Add a Support Resource',
        description='Help expand the directory by adding verified support resources.',
        button_text='Submit Resource',
        extra_context={
            'enable_map_picker': True,
            'default_county': default_county,
        }
    )


def contribute_idea(request):
    gate = _contributor_only_redirect(request)
    if gate:
        return gate

    form = IdeaSubmissionForm(request.POST or None, user=request.user)
    if request.method == 'POST':
        if form.is_valid():
            idea_obj = form.save(commit=False)
            if request.user.is_authenticated:
                idea_obj.user = request.user
            idea_obj.save()
            messages.success(request, 'Idea submitted. Thank you for your suggestion.')
            return redirect('contribute_idea')
        messages.error(request, 'Please review the highlighted fields and try again.')

    return _render_contribution_form_page(
        request,
        form=form,
        title='Share Idea - Voices Against Violence',
        heading='Share Your Idea',
        description='Suggest improvements, features, and campaigns to strengthen the platform.',
        button_text='Submit Idea',
    )


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION VIEWS  (Cognito-powered)
# ─────────────────────────────────────────────────────────────────────────────

@rate_limit(max_attempts=10, window_seconds=3600)
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username     = request.POST.get('username', '').strip()
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        email        = request.POST.get('email', '').strip().lower()
        phone_number = ''.join(request.POST.get('phone_number', '').split())
        user_type    = request.POST.get('user_type', 'victim')
        gender       = request.POST.get('gender', 'not specified')
        password1    = request.POST.get('password1', '')
        password2    = request.POST.get('password2', '')

        errors = []
        if not username:
            errors.append('Username is required.')
        if not first_name:
            errors.append('First name is required.')
        if not last_name:
            errors.append('Last name is required.')
        if not email:
            errors.append('Email is required.')
        if not phone_number:
            errors.append('Phone number is required (E.164 format: +254700000000).')
        if password1 != password2:
            errors.append('Passwords do not match.')
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters.')
        if phone_number and not phone_number.startswith('+'):
            errors.append('Phone number must start with + (e.g. +254712345678).')
        if username and User.objects.filter(username__iexact=username).exists():
            errors.append('This username is already taken. Please choose a unique username.')
        
        # Validate first_name format (letters, spaces, hyphens, apostrophes only)
        if first_name and not name_validator.regex.match(first_name):
            errors.append('First name should only contain letters, spaces, hyphens, and apostrophes.')
        
        # Validate last_name format (letters, spaces, hyphens, apostrophes only)
        if last_name and not name_validator.regex.match(last_name):
            errors.append('Last name should only contain letters, spaces, hyphens, and apostrophes.')
        
        # Validate phone_number format (digits, spaces, + only)
        if phone_number and not phone_validator.regex.match(phone_number):
            errors.append('Phone number should only contain numbers, spaces, and + symbol.')

        email_exists_local = User.objects.filter(email__iexact=email).exists() if email else False
        phone_exists_local = UserProfile.objects.filter(phone_number=phone_number).exists() if phone_number else False

        if email_exists_local:
            errors.append('This email address is already registered. Please sign in or use another email.')
        if phone_exists_local:
            errors.append('This phone number is already registered. Please sign in or use another phone number.')

        cognito = CognitoService()
        if email and not email_exists_local and cognito.email_exists(email):
            errors.append('This email address is already registered. Please sign in or use another email.')
        if phone_number and not phone_exists_local and cognito.phone_exists(phone_number):
            errors.append('This phone number is already registered. Please sign in or use another phone number.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'login.html', {'active_tab': 'signup', 'form_data': request.POST})

        result  = cognito.register_user(
            username=username, password=password1, email=email,
            phone_number=phone_number, user_type=user_type, gender=gender,
        )

        if not result['success']:
            messages.error(request, result.get('error', 'Registration failed. Please try again.'))
            return render(request, 'login.html', {'active_tab': 'signup', 'form_data': request.POST})

        delivery = result.get('delivery', {})
        delivery_medium = (delivery.get('medium') or '').upper()
        delivery_dest = delivery.get('destination') or ''

        request.session['pending_username'] = username
        request.session['pending_first_name'] = first_name
        request.session['pending_last_name'] = last_name
        request.session['pending_email']    = email
        request.session['pending_phone']    = phone_number
        request.session['pending_usertype'] = user_type

        user, _ = _get_or_create_user_case_insensitive(username)
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.is_active = False
        user.set_password(password1)
        user.save(update_fields=['first_name', 'last_name', 'email', 'is_active', 'password'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.phone_number = phone_number
        profile.user_type = user_type
        profile.save(update_fields=['phone_number', 'user_type'])

        if delivery_medium == 'EMAIL':
            messages.success(
                request,
                f'Account created successfully. Enter the 6-digit code sent to your email ({delivery_dest}).'
            )
        elif delivery_medium == 'SMS':
            messages.warning(
                request,
                'Account created successfully, but Cognito sent the 6-digit verification code by SMS '
                f'({delivery_dest}) instead of email. Enter that code below to continue.'
            )
        else:
            messages.info(
                request,
                'Account created successfully. Enter the 6-digit verification code sent to your email or phone.'
            )
        return redirect('verify_email')

    return render(request, 'login.html', {'active_tab': 'signup'})


@rate_limit(max_attempts=10, window_seconds=600)
def verify_email_view(request):
    username = request.session.get('pending_username')
    if not username:
        messages.error(request, 'Session expired. Please sign up again.')
        return redirect('signup')

    if request.method == 'POST':
        code    = request.POST.get('code', '').strip()
        cognito = CognitoService()
        result  = cognito.confirm_email(username=username, code=code)

        if not result['success']:
            messages.error(request, result.get('error', 'Invalid or expired code. Please try again.'))
            return render(request, 'verify_email.html', {'username': username})

        email     = request.session.get('pending_email', '')
        phone     = request.session.get('pending_phone', '')
        first_name = request.session.get('pending_first_name', '')
        last_name  = request.session.get('pending_last_name', '')
        user_type = request.session.get('pending_usertype', 'victim')

        user, _ = _get_or_create_user_case_insensitive(username)
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.is_active = True
        user.save(update_fields=['first_name', 'last_name', 'email', 'is_active'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.phone_number = phone
        profile.user_type = user_type
        profile.save(update_fields=['phone_number', 'user_type'])

        for k in ('pending_username', 'pending_first_name', 'pending_last_name', 'pending_email', 'pending_phone', 'pending_usertype'):
            request.session.pop(k, None)

        messages.success(request, 'Email verified. You can now sign in.')
        return redirect('login')

    return render(request, 'verify_email.html', {'username': username})


def resend_code_view(request):
    username = request.session.get('pending_username')
    if not username:
        return JsonResponse({'success': False, 'error': 'No pending registration found.'})
    result = CognitoService().resend_confirmation_code(username)
    return JsonResponse(result)


@rate_limit(max_attempts=5, window_seconds=300)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        cognito = CognitoService()
        result  = cognito.authenticate_user(username, password)

        if not result['success'] and result.get('challenge') == 'SMS_MFA':
            request.session['mfa_username'] = username
            request.session['mfa_session']  = result['session']
            # Preserve next param across MFA flow
            mfa_next = request.GET.get('next') or request.POST.get('next')
            if mfa_next:
                request.session['mfa_next'] = mfa_next
            messages.info(request, 'Enter the 6-digit code we sent to your phone.')
            return redirect('verify_mfa')

        if not result['success']:
            # Fall back to Django's local authentication (useful for locally-created admins)
            local_user = authenticate(request, username=username, password=password)
            if local_user:
                if not local_user.is_active:
                    messages.error(request, 'Account is disabled.')
                    return render(request, 'login.html', {'active_tab': 'login'})
                auth_login(request, local_user)
                profile = _get_or_create_profile(local_user)
                request.session['user_type'] = profile.user_type
                messages.success(request, f'Welcome back, {local_user.username}!')
                next_target = request.GET.get('next') or ('admin:index' if local_user.is_staff else 'home')
                return redirect(next_target)

            messages.error(request, result.get('error', 'Invalid username or password.'))
            return render(request, 'login.html', {'active_tab': 'login'})

        request.session['access_token']  = result['access_token']
        request.session['id_token']      = result['id_token']
        request.session['refresh_token'] = result['refresh_token']

        payload = cognito.verify_token(result['id_token'])
        email   = payload.get('email', '') if payload else ''

        user, _ = _get_or_create_user_case_insensitive(username, email=email)
        if email and user.email != email:
            user.email = email
            user.save(update_fields=['email'])

        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['is_active'])

        profile = UserProfile.objects.get_or_create(user=user)[0]
        request.session['user_type'] = profile.user_type

        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f'Welcome back, {user.username}!')
        next_target = request.GET.get('next') or ('admin:index' if user.is_staff else 'home')
        return redirect(next_target)

    return render(request, 'login.html', {'active_tab': 'login'})


def verify_mfa_view(request):
    username = request.session.get('mfa_username')
    session  = request.session.get('mfa_session')

    if not username or not session:
        messages.error(request, 'MFA session expired. Please sign in again.')
        return redirect('login')

    if request.method == 'POST':
        code    = request.POST.get('mfa_code', '').strip()
        cognito = CognitoService()
        result  = cognito.respond_to_sms_mfa(username, code, session)

        if not result['success']:
            messages.error(request, result.get('error', 'Invalid MFA code.'))
            return render(request, 'verify_mfa.html')

        request.session['access_token']  = result['access_token']
        request.session['id_token']      = result['id_token']
        request.session['refresh_token'] = result['refresh_token']

        for k in ('mfa_username', 'mfa_session'):
            request.session.pop(k, None)

        user, _ = _get_or_create_user_case_insensitive(username)
        profile = _get_or_create_profile(user)
        request.session['user_type'] = profile.user_type
        auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, 'Signed in successfully.')
        next_target = request.session.pop('mfa_next', None) or request.GET.get('next') or ('admin:index' if user.is_staff else 'home')
        return redirect(next_target)

    return render(request, 'verify_mfa.html')


@login_required
def logout_view(request):
    access_token = request.session.get('access_token')
    if access_token:
        CognitoService().sign_out(access_token)
    auth_logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('login')


@rate_limit(max_attempts=5, window_seconds=300)
def forgot_password_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        result   = CognitoService().forgot_password(username)
        if result['success']:
            request.session['reset_username'] = username
            messages.success(request, 'Reset code sent. Check your email or phone.')
            return redirect('reset_password')
        messages.error(request, result.get('error', 'We could not send a reset code. Please try again.'))
    return render(request, 'forgot_password.html')


@rate_limit(max_attempts=5, window_seconds=300)
def reset_password_view(request):
    username = request.session.get('reset_username')
    if not username:
        return redirect('forgot_password')

    if request.method == 'POST':
        code     = request.POST.get('code', '').strip()
        new_pass = request.POST.get('new_password', '')
        confirm  = request.POST.get('confirm_password', '')

        if new_pass != confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'reset_password.html')

        result = CognitoService().confirm_forgot_password(username, code, new_pass)
        if result['success']:
            user = User.objects.filter(username__iexact=username).first()
            if user:
                user.set_password(new_pass)
                user.save(update_fields=['password'])
            request.session.pop('reset_username', None)
            messages.success(request, 'Password reset successfully. You can now sign in.')
            return redirect('login')
        messages.error(request, result.get('error', 'Reset failed. Please try again.'))

    return render(request, 'reset_password.html')


@login_required
def myprofile_view(request):
    profile = _get_or_create_profile(request.user)

    if request.method == 'POST' and 'update_profile' in request.POST:
        profile_form = ProfileUpdateForm(request.POST, user=request.user, profile=profile)
        password_form = PasswordChangeForm(user=request.user)
        if profile_form.is_valid():
            new_email = profile_form.cleaned_data['email'].strip().lower()
            new_phone = ''.join((profile_form.cleaned_data['phone_number'] or '').split())
            new_user_type = profile_form.cleaned_data['user_type']

            current_email = (request.user.email or '').strip().lower()
            current_phone = ''.join((profile.phone_number or '').split())

            email_taken_local = User.objects.filter(email__iexact=new_email).exclude(pk=request.user.pk).exists()
            phone_taken_local = (
                UserProfile.objects.filter(phone_number=new_phone)
                .exclude(user=request.user)
                .exists()
                if new_phone else False
            )

            if email_taken_local:
                profile_form.add_error('email', 'This email address is already registered.')
            if phone_taken_local:
                profile_form.add_error('phone_number', 'This phone number is already registered.')

            cognito = CognitoService()
            cognito_email_exists = cognito.email_exists(new_email)
            cognito_phone_exists = cognito.phone_exists(new_phone) if new_phone else False

            if not email_taken_local and new_email != current_email and cognito_email_exists is True:
                profile_form.add_error('email', 'This email address is already registered.')
            if new_phone and not phone_taken_local and new_phone != current_phone and cognito_phone_exists is True:
                profile_form.add_error('phone_number', 'This phone number is already registered.')

            if not profile_form.errors:
                request.user.email = new_email
                request.user.save(update_fields=['email'])

                profile.phone_number = new_phone
                profile.user_type = new_user_type
                profile.save(update_fields=['phone_number', 'user_type'])
                request.session['user_type'] = profile.user_type

                access_token = _ensure_fresh_token(request)
                if access_token:
                    cognito_result = CognitoService().update_user_attributes(
                        access_token,
                        [
                            {'Name': 'email', 'Value': request.user.email},
                            {'Name': 'phone_number', 'Value': profile.phone_number or ''},
                            {'Name': 'custom:user_type', 'Value': profile.user_type},
                        ],
                    )
                    if not cognito_result.get('success'):
                        messages.warning(request, f"Profile saved locally, but Cognito sync failed: {cognito_result.get('error', 'unknown error')}")
                    else:
                        messages.success(request, 'Profile updated successfully.')
                else:
                    messages.warning(request, 'Profile updated locally. Sign in again to sync with Cognito.')

                return redirect('myprofile')

    elif request.method == 'POST' and 'change_password' in request.POST:
        profile_form = ProfileUpdateForm(
            user=request.user,
            profile=profile,
            initial={
                'email': request.user.email,
                'phone_number': profile.phone_number or '',
                'user_type': profile.user_type,
            },
        )
        password_form = PasswordChangeForm(request.POST, user=request.user)

        if password_form.is_valid():
            access_token = _ensure_fresh_token(request)
            if not access_token:
                messages.error(request, 'Session expired. Please sign in again before changing password.')
                return redirect('login')

            cognito_result = CognitoService().change_password(
                access_token,
                password_form.cleaned_data['current_password'],
                password_form.cleaned_data['new_password'],
            )

            if not cognito_result.get('success'):
                messages.error(request, cognito_result.get('error', 'Unable to change password right now.'))
            else:
                request.user.set_password(password_form.cleaned_data['new_password'])
                request.user.save(update_fields=['password'])
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password changed successfully.')
            return redirect('myprofile')

    else:
        profile_form = ProfileUpdateForm(
            user=request.user,
            profile=profile,
            initial={
                'email': request.user.email,
                'phone_number': profile.phone_number or '',
                'user_type': profile.user_type,
            },
        )
        password_form = PasswordChangeForm(user=request.user)

    reports = GBVReport.objects.filter(submitted_by=request.user).order_by('-created_at')
    progress_by_status = {
        GBVReport.STATUS_RECEIVED: 25,
        GBVReport.STATUS_ASSIGNED: 50,
        GBVReport.STATUS_IN_PROGRESS: 75,
        GBVReport.STATUS_CLOSED: 100,
    }
    report_progress = [
        {
            'report': report,
            'progress': progress_by_status.get(report.status, 0),
        }
        for report in reports
    ]

    return render(request, 'myprofile.html', {
        'profile_form': profile_form,
        'password_form': password_form,
        'report_progress': report_progress,
    })


@login_required
def change_role_view(request):
    if request.method != 'POST':
        return redirect('home')

    profile = _get_or_create_profile(request.user)
    old_role = profile.user_type
    profile.user_type = 'contributor' if profile.user_type == 'victim' else 'victim'
    profile.save(update_fields=['user_type'])
    request.session['user_type'] = profile.user_type

    audit_event(
        request,
        'role_changed',
        'UserProfile',
        request.user.id,
        {
            'from_role': old_role,
            'to_role': profile.user_type,
        },
    )

    access_token = _ensure_fresh_token(request)
    if access_token:
        cognito_result = CognitoService().update_user_attributes(
            access_token,
            [
                {'Name': 'custom:user_type', 'Value': profile.user_type},
            ],
        )
        if not cognito_result.get('success'):
            messages.warning(request, f"Role updated locally, but Cognito sync failed: {cognito_result.get('error', 'unknown error')}")
        else:
            messages.success(request, f"Role changed to {profile.get_user_type_display()}.")
    else:
        messages.success(request, f"Role changed to {profile.get_user_type_display()}.")

    next_url = request.POST.get('next') or 'myprofile'
    return redirect(next_url)


@login_required
def my_contributions_view(request):
    username = request.user.username
    user_full_name = request.user.get_full_name()
    article_q = Q(author_user=request.user) | Q(author=username)
    blog_q = Q(author_user=request.user) | Q(author=username)
    if user_full_name:
        article_q |= Q(author=user_full_name)
        blog_q |= Q(author=user_full_name)

    articles = Article.objects.filter(article_q).distinct().order_by('-created_at')
    blogs = Blog.objects.filter(blog_q).distinct().order_by('-created_at')
    stories = Story.objects.filter(user=request.user).order_by('-created_at')
    ideas = Idea.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'my_contributions.html', {
        'articles': articles,
        'blogs': blogs,
        'stories': stories,
        'ideas': ideas,
    })


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN API
# ─────────────────────────────────────────────────────────────────────────────

@staff_member_required
def admin_metrics_api(request):
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def shift_month(base_dt, delta_months):
        month_index = (base_dt.year * 12 + (base_dt.month - 1)) + delta_months
        year  = month_index // 12
        month = (month_index % 12) + 1
        return base_dt.replace(year=year, month=month, day=1)

    label_months = [shift_month(month_start, -idx) for idx in range(5, -1, -1)]
    label_keys   = [dt.strftime('%b %Y') for dt in label_months]
    window_start = label_months[0]

    def monthly_counts(queryset):
        bucket = (
            queryset.filter(created_at__gte=window_start)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(total=Count('id'))
            .order_by('month')
        )
        month_map = {entry['month'].strftime('%b %Y'): entry['total'] for entry in bucket}
        return [month_map.get(key, 0) for key in label_keys]

    gbv_series      = monthly_counts(GBVReport.objects.all())
    article_series  = monthly_counts(Article.objects.all())
    blog_series     = monthly_counts(Blog.objects.all())
    contact_series  = monthly_counts(Contact.objects.all())

    status_breakdown = {
        GBVReport.STATUS_RECEIVED: GBVReport.objects.filter(status=GBVReport.STATUS_RECEIVED).count(),
        GBVReport.STATUS_ASSIGNED: GBVReport.objects.filter(status=GBVReport.STATUS_ASSIGNED).count(),
        GBVReport.STATUS_IN_PROGRESS: GBVReport.objects.filter(status=GBVReport.STATUS_IN_PROGRESS).count(),
        GBVReport.STATUS_CLOSED: GBVReport.objects.filter(status=GBVReport.STATUS_CLOSED).count(),
    }

    y_max = max(gbv_series + contact_series + article_series + blog_series + [5])

    try:
        _Thread = apps.get_model("django_ai_assistant", "Thread")
        _Message = apps.get_model("django_ai_assistant", "Message")
        ai_threads = _Thread.objects.count()
        ai_messages = _Message.objects.count()
    except Exception:
        ai_threads = None
        ai_messages = None

    payload = {
        'summary': {
            'gbv_reports':      GBVReport.objects.count(),
            'resources':        Resource.objects.count(),
            'contacts':         Contact.objects.count(),
            'articles':         Article.objects.count(),
            'blogs':            Blog.objects.count(),
            'users':            User.objects.count(),
            'stories':          Story.objects.count(),
            'ideas':            Idea.objects.count(),
            'pending_articles': Article.objects.filter(published=False).count(),
            'pending_blogs':    Blog.objects.filter(published=False).count(),
            'status_breakdown': status_breakdown,
            'ai_threads':       ai_threads,
            'ai_messages':      ai_messages,
        },
        'labels': label_keys,
        'y_max':  y_max,
        'series': {
            'gbv_reports':      gbv_series,
            'articles':         article_series,
            'blogs':            blog_series,
            'contacts':         contact_series,
        },
    }
    return JsonResponse(payload)


def _parse_query_date(raw_value):
    if not raw_value:
        return None
    try:
        return dt_date.fromisoformat(raw_value)
    except ValueError:
        return None


def _is_truthy_query_flag(raw_value):
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def _filtered_gbv_reports_queryset(request):
    qs = GBVReport.objects.select_related("submitted_by").order_by("-created_at")

    start_date = _parse_query_date(request.GET.get("start_date"))
    end_date = _parse_query_date(request.GET.get("end_date"))
    report_type = (request.GET.get("report_type") or "").strip().lower()
    status = (request.GET.get("status") or "").strip().lower()

    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    if report_type in {choice[0] for choice in GBVReport.REPORT_TYPES}:
        qs = qs.filter(report_type=report_type)
    if status in {choice[0] for choice in GBVReport.STATUS_CHOICES}:
        qs = qs.filter(status=status)

    return qs


def _gbv_sla_targets_hours():
    return {
        GBVReport.STATUS_RECEIVED: 24,
        GBVReport.STATUS_ASSIGNED: 72,
        GBVReport.STATUS_IN_PROGRESS: 168,
    }


def _median_int(values):
    if not values:
        return 0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return int(ordered[mid])
    return int(round((ordered[mid - 1] + ordered[mid]) / 2))


def _build_gbv_sla_snapshot(qs):
    now = timezone.now()
    targets = _gbv_sla_targets_hours()

    overdue_by_status = {
        GBVReport.STATUS_RECEIVED: 0,
        GBVReport.STATUS_ASSIGNED: 0,
        GBVReport.STATUS_IN_PROGRESS: 0,
        GBVReport.STATUS_CLOSED: 0,
    }
    age_buckets = {
        "0_24h": 0,
        "25_72h": 0,
        "73_168h": 0,
        "169h_plus": 0,
    }
    age_values_by_status = {
        GBVReport.STATUS_RECEIVED: [],
        GBVReport.STATUS_ASSIGNED: [],
        GBVReport.STATUS_IN_PROGRESS: [],
        GBVReport.STATUS_CLOSED: [],
    }

    rows = []
    overdue_total = 0
    for report in qs:
        baseline = report.status_updated_at or report.created_at
        age_hours = max(int((now - baseline).total_seconds() // 3600), 0)
        target_hours = targets.get(report.status)

        is_overdue = bool(target_hours is not None and age_hours > target_hours)
        overdue_hours = max(age_hours - target_hours, 0) if target_hours is not None else 0

        if age_hours <= 24:
            age_buckets["0_24h"] += 1
        elif age_hours <= 72:
            age_buckets["25_72h"] += 1
        elif age_hours <= 168:
            age_buckets["73_168h"] += 1
        else:
            age_buckets["169h_plus"] += 1

        age_values_by_status[report.status].append(age_hours)

        if is_overdue:
            overdue_total += 1
            overdue_by_status[report.status] += 1

        rows.append({
            "report": report,
            "age_hours": age_hours,
            "sla_target_hours": target_hours,
            "is_overdue": is_overdue,
            "overdue_hours": overdue_hours,
        })

    median_age_hours_by_status = {
        status: _median_int(values)
        for status, values in age_values_by_status.items()
    }

    return {
        "rows": rows,
        "summary": {
            "total_reports": len(rows),
            "open_reports": sum(1 for row in rows if row["report"].status != GBVReport.STATUS_CLOSED),
            "overdue_total": overdue_total,
            "overdue_by_status": overdue_by_status,
            "age_buckets": age_buckets,
            "median_age_hours_by_status": median_age_hours_by_status,
        },
    }


@staff_member_required
def admin_gbv_sla_api(request):
    qs = _filtered_gbv_reports_queryset(request)
    snapshot = _build_gbv_sla_snapshot(qs)

    payload = {
        "generated_at": timezone.localtime().isoformat(),
        "filters": {
            "start_date": request.GET.get("start_date") or "",
            "end_date": request.GET.get("end_date") or "",
            "report_type": request.GET.get("report_type") or "",
            "status": request.GET.get("status") or "",
        },
        "summary": snapshot["summary"],
    }
    return JsonResponse(payload)


def _filtered_feedback_queryset(request):
    qs = SupportFeedback.objects.select_related("report").order_by("-created_at")

    start_date = _parse_query_date(request.GET.get("start_date"))
    end_date = _parse_query_date(request.GET.get("end_date"))
    report_type = (request.GET.get("report_type") or "").strip().lower()
    report_status = (request.GET.get("report_status") or "").strip().lower()

    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    if report_type in {choice[0] for choice in GBVReport.REPORT_TYPES}:
        qs = qs.filter(report__report_type=report_type)
    if report_status in {choice[0] for choice in GBVReport.STATUS_CHOICES}:
        qs = qs.filter(report__status=report_status)

    return qs


def _filtered_audit_logs_queryset(request):
    qs = AuditLog.objects.select_related("actor").order_by("-created_at")

    start_date = _parse_query_date(request.GET.get("start_date"))
    end_date = _parse_query_date(request.GET.get("end_date"))

    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    return qs


def _filtered_ai_messages_queryset(request):
    message_model = apps.get_model("django_ai_assistant", "Message")
    assistant_id = (request.GET.get("assistant_id") or "").strip()

    qs = message_model.objects.select_related("thread", "thread__created_by").order_by("-created_at")

    start_date = _parse_query_date(request.GET.get("start_date"))
    end_date = _parse_query_date(request.GET.get("end_date"))

    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    if assistant_id:
        qs = qs.filter(thread__assistant_id=assistant_id)

    return qs


@staff_member_required
def export_gbv_reports_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="gbv_reports_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "submitted_at",
        "status",
        "report_type",
        "county",
        "location",
        "incident_date",
        "description",
        "gender",
        "relationship_to_perpetrator",
        "anonymous",
        "name",
        "phone",
        "email",
        "id_number",
        "followup_opt_in",
        "followup_email",
        "submitted_by",
        "consent",
        "status_updated_at",
    ])

    for report in _filtered_gbv_reports_queryset(request).select_related("submitted_by"):
        writer.writerow([
            report.id,
            timezone.localtime(report.created_at).isoformat(),
            report.get_status_display(),
            report.get_report_type_display(),
            report.county or "",
            report.location,
            report.incident_date.isoformat() if report.incident_date else "",
            report.description,
            report.get_gender_display() if report.gender else "",
            report.get_relationship_to_perpetrator_display() if report.relationship_to_perpetrator else "",
            report.anonymous,
            "" if report.anonymous else (report.name or ""),
            "" if report.anonymous else (report.phone or ""),
            "" if report.anonymous else (report.email or ""),
            "" if report.anonymous else (report.id_number or ""),
            report.followup_opt_in,
            report.followup_email or "",
            report.submitted_by.username if report.submitted_by else "",
            report.consent,
            timezone.localtime(report.status_updated_at).isoformat(),
        ])

    return response


@staff_member_required
def export_support_feedback_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="support_feedback_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "created_at",
        "report_id",
        "report_status",
        "report_type",
        "comment",
    ])

    for feedback in _filtered_feedback_queryset(request):
        writer.writerow([
            feedback.id,
            timezone.localtime(feedback.created_at).isoformat(),
            feedback.report_id,
            feedback.report.status,
            feedback.report.report_type,
            feedback.comment,
        ])

    return response


@staff_member_required
def export_audit_logs_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="audit_logs_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "created_at",
        "action",
        "actor",
        "target_type",
        "target_id",
        "ip_address",
        "metadata",
    ])

    for log in _filtered_audit_logs_queryset(request):
        writer.writerow([
            log.id,
            timezone.localtime(log.created_at).isoformat(),
            log.action,
            log.actor.username if log.actor else "",
            log.target_type,
            log.target_id,
            log.ip_address or "",
            json.dumps(log.metadata or {}, ensure_ascii=True),
        ])

    return response


@staff_member_required
def export_ai_reports_csv(request):
    """Export AI chat metadata only — message content is private and not included."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="ai_session_metadata_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "thread_id",
        "assistant_id",
        "thread_created_by",
        "thread_created_at",
        "message_count",
    ])

    Thread = apps.get_model("django_ai_assistant", "Thread")
    Message = apps.get_model("django_ai_assistant", "Message")

    start_date = _parse_query_date(request.GET.get("start_date"))
    end_date = _parse_query_date(request.GET.get("end_date"))

    qs = Thread.objects.filter(assistant_id="gbv_support_assistant").select_related("created_by")
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    for thread in qs.order_by("-created_at"):
        msg_count = Message.objects.filter(thread=thread).count()
        writer.writerow([
            thread.id,
            thread.assistant_id,
            thread.created_by.username if thread.created_by else "",
            timezone.localtime(thread.created_at).isoformat(),
            msg_count,
        ])

    return response


@staff_member_required
def export_gbv_sla_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="gbv_sla_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "created_at",
        "status",
        "status_updated_at",
        "age_hours",
        "sla_target_hours",
        "is_overdue",
        "overdue_hours",
        "report_type",
        "location",
        "incident_date",
        "submitted_by",
    ])

    snapshot = _build_gbv_sla_snapshot(_filtered_gbv_reports_queryset(request))
    overdue_only = _is_truthy_query_flag(request.GET.get("overdue_only"))

    for row in snapshot["rows"]:
        if overdue_only and not row["is_overdue"]:
            continue
        report = row["report"]
        writer.writerow([
            report.id,
            timezone.localtime(report.created_at).isoformat(),
            report.status,
            timezone.localtime(report.status_updated_at).isoformat() if report.status_updated_at else "",
            row["age_hours"],
            row["sla_target_hours"] if row["sla_target_hours"] is not None else "",
            "yes" if row["is_overdue"] else "no",
            row["overdue_hours"],
            report.report_type,
            report.location,
            report.incident_date.isoformat() if report.incident_date else "",
            report.submitted_by.username if report.submitted_by else "",
        ])

    return response


@staff_member_required
def export_articles_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="articles_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "title",
        "author",
        "author_user",
        "category",
        "published",
        "views",
        "read_time",
        "created_at",
        "updated_at",
    ])

    for article in Article.objects.all().order_by('-created_at'):
        writer.writerow([
            article.id,
            article.title,
            article.author,
            article.author_user.username if article.author_user else "",
            article.category,
            "yes" if article.published else "no",
            article.views or 0,
            article.read_time or 0,
            timezone.localtime(article.created_at).isoformat(),
            timezone.localtime(article.updated_at).isoformat() if article.updated_at else "",
        ])

    return response


@staff_member_required
def export_blogs_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="blogs_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "title",
        "author",
        "author_user",
        "category",
        "published",
        "views",
        "read_time",
        "created_at",
        "updated_at",
    ])

    for blog in Blog.objects.all().order_by('-created_at'):
        writer.writerow([
            blog.id,
            blog.title,
            blog.author,
            blog.author_user.username if blog.author_user else "",
            blog.category,
            "yes" if blog.published else "no",
            blog.views or 0,
            blog.read_time or 0,
            timezone.localtime(blog.created_at).isoformat(),
            timezone.localtime(blog.updated_at).isoformat() if blog.updated_at else "",
        ])

    return response


@staff_member_required
def export_contacts_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="contacts_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "name",
        "email",
        "subject",
        "message",
        "created_at",
    ])

    for contact in Contact.objects.all().order_by('-created_at'):
        writer.writerow([
            contact.id,
            contact.name,
            contact.email,
            contact.subject,
            contact.message or "",
            timezone.localtime(contact.created_at).isoformat(),
        ])

    return response


@staff_member_required
def export_users_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="users_export.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "id",
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
        "user_type",
        "phone_number",
        "profile_created_at",
    ])

    for profile in UserProfile.objects.select_related('user').all().order_by('-user__date_joined'):
        user = profile.user
        writer.writerow([
            user.id,
            user.username,
            user.email,
            user.first_name,
            user.last_name,
            "yes" if user.is_staff else "no",
            "yes" if user.is_active else "no",
            timezone.localtime(user.date_joined).isoformat(),
            profile.user_type or "",
            profile.phone_number or "",
            timezone.localtime(profile.created_at).isoformat(),
        ])

    return response


def route_api(request):
    """
    Returns a JSON route between two lat/lng points using OSRM (free, no API key).
    GET params: origin_lat, origin_lng, dest_lat, dest_lng
    """
    origin_lat = request.GET.get("origin_lat")
    origin_lng = request.GET.get("origin_lng")
    dest_lat   = request.GET.get("dest_lat")
    dest_lng   = request.GET.get("dest_lng")

    if not all([origin_lat, origin_lng, dest_lat, dest_lng]):
        # Backward compatible input style: origin="lng,lat" destination="lng,lat"
        origin = request.GET.get("origin")
        destination = request.GET.get("destination")
        if origin and destination:
            try:
                origin_lng, origin_lat = origin.split(",")
                dest_lng, dest_lat = destination.split(",")
            except ValueError:
                return JsonResponse({"error": "Invalid origin/destination format. Use 'lng,lat'."}, status=400)

    if not all([origin_lat, origin_lng, dest_lat, dest_lng]):
        return JsonResponse({"error": "Missing parameters: origin_lat, origin_lng, dest_lat, dest_lng"}, status=400)

    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
            f"?overview=full&geometries=geojson&steps=true"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "VAV-App/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if data.get("code") != "Ok" or not data.get("routes"):
            return JsonResponse({"error": "No route found."}, status=404)

        route = data["routes"][0]
        return JsonResponse({
            "code": "Ok",
            "profile_used": "driving",
            "routes": data.get("routes", []),
            "distance_m":  route.get("distance", 0),
            "duration_s":  route.get("duration", 0),
            "geometry":    route.get("geometry", {"type": "LineString", "coordinates": []}),
            "steps": [
                {
                    "instruction": s["maneuver"]["type"],
                    "distance_m":  s["distance"],
                    "duration_s":  s["duration"],
                }
                for leg in route.get("legs", [])
                for s in leg.get("steps", [])
            ],
        })

    except urllib.error.URLError as e:
        fallback_geometry = {
            "type": "LineString",
            "coordinates": [
                [float(origin_lng), float(origin_lat)],
                [float(dest_lng), float(dest_lat)],
            ],
        }
        return JsonResponse({
            "code": "Ok",
            "fallback": True,
            "profile_used": "driving",
            "error": f"Routing service unavailable: {e}",
            "routes": [{"geometry": fallback_geometry, "distance": 0, "duration": 0}],
            "geometry": fallback_geometry,
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)