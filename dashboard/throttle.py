"""Simple login throttling: block repeated failed logins for a username from one address."""

import hashlib
import os

from django.conf import settings
from django.core.cache import cache


def client_ip(request):
    # Behind a hosting proxy (e.g. Render) the real client is the last address
    # the proxy appended. Only trust the header when told we're behind one.
    if os.environ.get("TRUST_PROXY_HEADERS", "").lower() in {"1", "true", "yes"}:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key(request, username):
    raw = f"{(username or '').strip().lower()}|{client_ip(request)}"
    return "login-fail:" + hashlib.sha256(raw.encode()).hexdigest()


def is_locked(request, username):
    return cache.get(_key(request, username), 0) >= settings.LOGIN_MAX_ATTEMPTS


def record_failure(request, username):
    key = _key(request, username)
    if cache.add(key, 1, settings.LOGIN_LOCKOUT_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, settings.LOGIN_LOCKOUT_SECONDS)


def clear(request, username):
    cache.delete(_key(request, username))
