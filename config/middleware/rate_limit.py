"""
Simple rate limiting middleware — cached counters keyed by IP.

Compatible with LocMem and Redis caches.

Login-specific rules:
    - Counts failed login POST attempts per IP.
    - On successful login, counter is NOT reset (still tracks window).
    - Blocks IP for RATE_LIMIT_LOGIN_WINDOW_SECONDS after limit exceeded.

General rules:
    - Applies to all requests.
    - Different limits for anonymous vs authenticated.
    - Skips static, media, admin login page (Django protects that).

All thresholds come from settings (settings_production.py).
"""
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.urls import reverse


def _get_client_ip(request):
    """Extract real client IP, honoring proxies."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _is_static_or_media(path):
    """Skip rate limiting for static/media/health-check paths."""
    static_url = getattr(settings, 'STATIC_URL', '/static/')
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    return (
        path.startswith(static_url)
        or path.startswith(media_url)
        or path == '/healthz/'
    )


class RateLimitMiddleware:
    """
    Two-layer rate limiting:

    1. Login brute-force: POSTs to LOGIN_URL.
       Failed attempts counter per IP.
       On successful login, no counter increment.

    2. General: token bucket per IP per minute.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if _is_static_or_media(path):
            return self.get_response(request)

        ip = _get_client_ip(request)

        # ---------- Login brute-force check ----------
        login_url = reverse('accounts:login')
        if request.method == 'POST' and path == login_url:
            block_key = f'rl:login:block:{ip}'
            if cache.get(block_key):
                return self._blocked_response(
                    "Too many failed attempts. 5 minute baad try karein."
                )

            response = self.get_response(request)

            # If login failed (status 200 with form errors), increment counter
            # Successful login usually redirects (302) — do not increment.
            if response.status_code == 200:
                fail_key = f'rl:login:fail:{ip}'
                fails = (cache.get(fail_key) or 0) + 1
                window = getattr(settings, 'RATE_LIMIT_LOGIN_WINDOW_SECONDS', 300)
                limit = getattr(settings, 'RATE_LIMIT_LOGIN_ATTEMPTS', 5)
                cache.set(fail_key, fails, window)
                if fails >= limit:
                    cache.set(block_key, True, window)
            return response

        # ---------- General rate limit ----------
        limit = (
            300 if request.user.is_authenticated
            else 60
        )
        window = getattr(settings, 'RATE_LIMIT_WINDOW_SECONDS', 60)
        current_minute = int(time.time() // window)
        key = f'rl:gen:{ip}:{current_minute}'

        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, window)
            count = 1

        if count > limit:
            return self._blocked_response(
                "Too many requests. Ek minute ruk kar try karein."
            )

        return self.get_response(request)

    def _blocked_response(self, message):
        """Return 429 for both HTML and JSON requests."""
        return HttpResponse(
            message,
            status=429,
            content_type='text/plain',
        )