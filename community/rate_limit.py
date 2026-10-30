from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render


RATE_LIMITS = {
    "thread_write": {"limit": 6, "window": 600},
    "reply": {"limit": 12, "window": 600},
    "like": {"limit": 40, "window": 60},
    "delete": {"limit": 5, "window": 600},
}


def rate_limit_key(request, action):
    if request.user.is_authenticated:
        identifier = f"user-{request.user.pk}"
    else:
        identifier = f"ip-{request.META.get('REMOTE_ADDR', 'unknown')}"
    return f"community:rate-limit:{action}:{identifier}"


def expects_json(request):
    return (
        request.headers.get("HX-Request") == "true"
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
    )


def rate_limited_response(request, window):
    message = "Terlalu banyak permintaan. Coba lagi sebentar lagi."
    headers = {"Retry-After": str(window)}
    if expects_json(request):
        return JsonResponse({"detail": message}, status=429, headers=headers)
    return render(
        request,
        "community/rate_limited.html",
        {"message": message},
        status=429,
        headers=headers,
    )


def limit_post_requests(action):
    """Limit a Community POST action per authenticated user in Django's cache."""

    config = RATE_LIMITS[action]

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return view(request, *args, **kwargs)

            key = rate_limit_key(request, action)
            if cache.add(key, 1, timeout=config["window"]):
                return view(request, *args, **kwargs)

            try:
                attempts = cache.incr(key)
            except ValueError:
                cache.add(key, 1, timeout=config["window"])
                attempts = 1

            if attempts > config["limit"]:
                return rate_limited_response(request, config["window"])
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
