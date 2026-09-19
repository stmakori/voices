from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
import time

class SimpleRateLimitMiddleware:
    """
    Basic IP+path limiter. Tune in settings:
    RATE_LIMIT_MAX_REQUESTS=30
    RATE_LIMIT_WINDOW_SECONDS=60
    RATE_LIMIT_PATH_PREFIXES=('/login', '/signup', '/report')
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        prefixes = getattr(request, "rate_limit_prefixes", None)
        if prefixes is None:
            prefixes = getattr(settings, "RATE_LIMIT_PATH_PREFIXES", ("/login", "/signup", "/report"))
        max_req = getattr(settings, "RATE_LIMIT_MAX_REQUESTS", 30)
        window = getattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)

        path = request.path.lower()
        if any(path.startswith(p) for p in prefixes):
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()
            key = f"rl:{ip}:{path}:{int(time.time() // window)}"
            count = cache.get(key, 0) + 1
            cache.set(key, count, timeout=window)
            if count > max_req:
                return JsonResponse({"error": "Too many requests. Please wait."}, status=429)

        return self.get_response(request)


class FirstVisitLoginGateMiddleware:
    """
    Public-access middleware: by default, only unauthenticated users can access home, contact, about.
    All other pages require authentication and redirect to register.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Paths that are PUBLIC and don't require authentication
        self.public_paths = {
            '/',
            '/home/',
            '/about/',
            '/contact/',
            '/login/',
            '/signup/',
            '/forgot-password/',
            '/reset-password/',
            '/verify-email/',
            '/verify-mfa/',
        }
        # Static/admin prefixes always allowed through
        self.always_allowed_prefixes = (
            '/static/',
            '/media/',
            '/admin/',
            '/summernote/',
            '/django_ai_assistant/',
        )

    def __call__(self, request):
        path = request.path

        # Always allow static/admin/media
        if any(path.startswith(prefix) for prefix in self.always_allowed_prefixes):
            return self.get_response(request)

        # Allow authenticated users everywhere
        if request.user.is_authenticated:
            return self.get_response(request)

        # For unauthenticated users, only allow public paths
        if path not in self.public_paths:
            # Redirect to register page
            register_url = reverse('signup')
            return redirect(f"{register_url}?next={request.get_full_path()}")

        # Public path — let them through
        return self.get_response(request)