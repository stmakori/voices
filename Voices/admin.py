from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.utils import timezone
from django import forms
from django.conf import settings
from django.db import transaction
from django.apps import apps
import django.db.models as djmodels
from django.forms import Textarea
from django.utils.html import format_html
try:
    from django_summernote.admin import SummernoteModelAdmin
except Exception:
    SummernoteModelAdmin = admin.ModelAdmin
from .models import (
    GBVReport, GBVReportStatusUpdate, Resource,
    AuditLog, SupportFeedback,
    Article, Blog, Story, Idea, Contact, Team, UserProfile,
)

# Unregister django_ai_assistant models so admin cannot view chat content
for _ai_model_name in ("Thread", "Message"):
    try:
        _ai_model = apps.get_model("django_ai_assistant", _ai_model_name)
        admin.site.unregister(_ai_model)
    except Exception:
        pass


def _transfer_user_relations(source_user, target_user):
    for relation in User._meta.related_objects:
        related_model = relation.related_model
        field_name = relation.field.name

        if related_model is UserProfile and field_name == "user":
            continue

        queryset = related_model.objects.filter(**{field_name: source_user})
        if not queryset.exists():
            continue

        if relation.one_to_one and related_model.objects.filter(**{field_name: target_user}).exists():
            continue

        queryset.update(**{field_name: target_user})


def _merge_user_profile(source_user, target_user):
    source_profile = UserProfile.objects.filter(user=source_user).first()
    if not source_profile:
        return

    target_profile = UserProfile.objects.filter(user=target_user).first()
    if target_profile:
        if not target_profile.phone_number and source_profile.phone_number:
            target_profile.phone_number = source_profile.phone_number
        if source_profile.user_type and target_profile.user_type != source_profile.user_type:
            target_profile.user_type = source_profile.user_type
        target_profile.save(update_fields=["phone_number", "user_type"])
        source_profile.delete()
    else:
        source_profile.user = target_user
        source_profile.save(update_fields=["user"])


class ResourceAdminForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["latitude"].widget.attrs.update({"id": "id_latitude", "step": "any"})
        self.fields["longitude"].widget.attrs.update({"id": "id_longitude", "step": "any"})

class GBVReportStatusUpdateInline(admin.TabularInline):
    model = GBVReportStatusUpdate
    extra = 0
    readonly_fields = ("created_at",)
    formfield_overrides = {
        djmodels.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 60})}
    }

@admin.register(GBVReport)
class GBVReportAdmin(admin.ModelAdmin):
    list_display = ("id", "submitted_by", "status", "status_updated_at", "created_at")
    list_filter = ("status", "created_at")
    inlines = [GBVReportStatusUpdateInline]
    actions = ["mark_assigned", "mark_in_progress", "mark_closed"]

    def mark_assigned(self, request, queryset):
        for r in queryset:
            r.set_status(GBVReport.STATUS_ASSIGNED, request.user, "Updated in admin")
    def mark_in_progress(self, request, queryset):
        for r in queryset:
            r.set_status(GBVReport.STATUS_IN_PROGRESS, request.user, "Updated in admin")
    def mark_closed(self, request, queryset):
        for r in queryset:
            r.set_status(GBVReport.STATUS_CLOSED, request.user, "Updated in admin")

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    form = ResourceAdminForm
    change_form_template = "admin/voices/resource/change_form.html"
    list_display = ("name", "resource_type", "location", "latitude", "longitude", "is_verified", "last_confirmed_at")
    list_filter = ("is_verified", "resource_type")
    search_fields = ("name", "address", "phone")

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.setdefault("location", getattr(settings, "RESOURCE_DEFAULT_COUNTY", "Nakuru County"))
        return initial

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context = dict(context)
        context["RESOURCE_DEFAULT_COUNTY"] = getattr(settings, "RESOURCE_DEFAULT_COUNTY", "Nakuru County")
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    change_form_template = "admin/auth/user/change_form.html"
    list_display = ("username", "email", "first_name", "last_name", "is_active", "is_staff", "date_joined")
    search_fields = ("username", "first_name", "last_name", "email")
    filter_vertical = ("groups", "user_permissions")
    actions = ("merge_selected_users", "delete_selected_users_safely")

    @admin.action(description="Merge selected users into the first selected user")
    def merge_selected_users(self, request, queryset):
        users = list(queryset.order_by("id"))
        if len(users) < 2:
            self.message_user(request, "Select at least two users to merge.", level=messages.WARNING)
            return

        target = users[0]
        merged_count = 0

        with transaction.atomic():
            for source in users[1:]:
                if source.pk == target.pk:
                    continue
                _transfer_user_relations(source, target)
                _merge_user_profile(source, target)
                source.delete()
                merged_count += 1

        self.message_user(request, f"Merged {merged_count} user(s) into {target.username}.", level=messages.SUCCESS)

    @admin.action(description="Delete selected users safely")
    def delete_selected_users_safely(self, request, queryset):
        deleted_count = 0

        with transaction.atomic():
            for user in queryset.order_by("id"):
                profile = UserProfile.objects.filter(user=user).first()
                if profile:
                    profile.delete()
                user.delete()
                deleted_count += 1

        self.message_user(request, f"Deleted {deleted_count} user(s) safely.", level=messages.SUCCESS)

def _status_badge(obj):
    colours = {'pending': '#f59e0b', 'approved': '#10b981', 'rejected': '#ef4444'}
    labels  = {'pending': 'Pending', 'approved': 'Approved', 'rejected': 'Rejected'}
    c = colours.get(obj.status, '#6b7280')
    l = labels.get(obj.status, obj.status.title())
    return format_html(
        '<span style="background:{};color:#fff;padding:2px 10px;border-radius:999px;'
        'font-size:0.75rem;font-weight:700;letter-spacing:0.03em">{}</span>', c, l
    )
_status_badge.short_description = 'Status'
_status_badge.admin_order_field = 'status'


def _review_save(admin_self, request, obj, form, change):
    """Shared save_model logic: auto-set reviewer info and sync published flag."""
    if 'status' in form.changed_data:
        obj.reviewed_by = request.user
        obj.reviewed_at = timezone.now()
    if hasattr(obj, 'published'):
        if obj.status == 'approved':
            obj.published = True
        elif obj.status in ('pending', 'rejected'):
            obj.published = False
    admin_self.__class__.__bases__[0].save_model(admin_self, request, obj, form, change)


def _approve_action(modeladmin, request, queryset):
    now = timezone.now()
    updated = queryset.update(
        status='approved', published=True,
        reviewed_by=request.user, reviewed_at=now,
    )
    modeladmin.message_user(request, f"{updated} contribution(s) approved and published.", messages.SUCCESS)
_approve_action.short_description = "✓ Approve selected (publish)"


def _reject_action(modeladmin, request, queryset):
    now = timezone.now()
    has_published = queryset.filter(published=True).exists() if hasattr(queryset.model, 'published') else False
    updated = queryset.update(
        status='rejected', reviewed_by=request.user, reviewed_at=now,
    )
    if has_published:
        queryset.update(published=False)
    modeladmin.message_user(
        request,
        f"{updated} contribution(s) marked as rejected. "
        "Open each item to add a personalised feedback note.",
        messages.WARNING,
    )
_reject_action.short_description = "✗ Reject selected"


_REVIEW_FIELDSET = ('Review Decision', {
    'fields': ('status', 'review_note', 'reviewed_by', 'reviewed_at'),
    'classes': ('wide',),
    'description': (
        'Set the review outcome. <strong>Approving</strong> automatically publishes the '
        'contribution; <strong>Rejecting</strong> hides it. '
        'The feedback note is visible to the contributor on their My Contributions page.'
    ),
})


@admin.register(Article)
class ArticleAdmin(SummernoteModelAdmin):
    list_display = ("title", "author", "author_user", "category", _status_badge, "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "author", "author_user__username", "content")
    summernote_fields = ("content",)
    readonly_fields = ("reviewed_by", "reviewed_at", "published")
    actions = [_approve_action, _reject_action]
    fieldsets = (
        ('Article Content', {
            'fields': (
                'title', 'author', 'author_user', 'category',
                'content', 'image', 'anonymous', 'read_time', 'views', 'published',
            ),
        }),
        _REVIEW_FIELDSET,
    )

    def save_model(self, request, obj, form, change):
        _review_save(self, request, obj, form, change)


@admin.register(Blog)
class BlogAdmin(SummernoteModelAdmin):
    list_display = ("title", "author", "author_user", "category", _status_badge, "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "author", "author_user__username", "content")
    summernote_fields = ("content",)
    readonly_fields = ("reviewed_by", "reviewed_at", "published")
    actions = [_approve_action, _reject_action]
    fieldsets = (
        ('Blog Content', {
            'fields': (
                'title', 'author', 'author_user', 'category',
                'content', 'image', 'anonymous', 'read_time', 'views', 'published',
            ),
        }),
        _REVIEW_FIELDSET,
    )

    def save_model(self, request, obj, form, change):
        _review_save(self, request, obj, form, change)


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ("user", _status_badge, "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "story")
    readonly_fields = ("reviewed_by", "reviewed_at", "published")
    actions = [_approve_action, _reject_action]
    fieldsets = (
        ('Story Content', {
            'fields': ('user', 'story', 'consent', 'published'),
        }),
        _REVIEW_FIELDSET,
    )

    def save_model(self, request, obj, form, change):
        _review_save(self, request, obj, form, change)


@admin.register(Idea)
class IdeaAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "user", _status_badge, "created_at")
    list_filter = ("status", "category", "created_at")
    search_fields = ("title", "description", "user__username")
    readonly_fields = ("reviewed_by", "reviewed_at")
    actions = [_approve_action, _reject_action]
    fieldsets = (
        ('Idea Content', {
            'fields': ('user', 'title', 'category', 'description'),
        }),
        _REVIEW_FIELDSET,
    )

    def save_model(self, request, obj, form, change):
        _review_save(self, request, obj, form, change)

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("display_user", "name", "email", "subject", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name", "email", "subject", "user__username")

    def display_user(self, obj):
        if obj.user:
            return format_html(
                '<span style="font-weight:600;color:#5A2D7A">{}</span>',
                obj.user.username,
            )
        # Try to match a registered user by email
        from django.contrib.auth.models import User as AuthUser
        try:
            matched = AuthUser.objects.get(email=obj.email)
            return format_html(
                '<span style="color:#6b7280">{} <em style="font-size:.75rem">(matched)</em></span>',
                matched.username,
            )
        except (AuthUser.DoesNotExist, AuthUser.MultipleObjectsReturned):
            pass
        return format_html('<span style="color:#9ca3af;font-style:italic">{}</span>', "Guest")

    display_user.short_description = "User"
    display_user.admin_order_field = "user"

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "email")
    search_fields = ("name", "role")

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "user_type", "phone_number", "created_at")
    list_filter = ("user_type",)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "target_type", "target_id", "ip_address", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("action", "actor__username", "target_type", "target_id", "ip_address")
    readonly_fields = (
        "action", "actor", "target_type", "target_id",
        "ip_address", "metadata", "created_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(SupportFeedback)
class SupportFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "report",
        "report_status",
        "report_type",
        "short_comment",
        "created_at",
    )
    list_filter = ("created_at", "report__status", "report__report_type")
    search_fields = (
        "report__id",
        "report__location",
        "report__submitted_by__username",
        "comment",
    )
    exclude = ("score",)
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("report", "report__submitted_by")

    def report_status(self, obj):
        return obj.report.get_status_display()

    report_status.short_description = "Report status"

    def report_type(self, obj):
        return obj.report.get_report_type_display()

    report_type.short_description = "Report type"

    def short_comment(self, obj):
        text = (obj.comment or "").strip()
        if not text:
            return "-"
        return text[:60] + ("..." if len(text) > 60 else "")

    short_comment.short_description = "Comment"
