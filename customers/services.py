"""Customer sessions and simple limits on how often the public forms can be used."""

import hashlib

from django.core.cache import cache
from django.utils import timezone

from dashboard.throttle import client_ip

from .models import Customer

# A handful of messages or sign ups an hour from one address is plenty for real people.
FORM_LIMIT = 5
FORM_WINDOW_SECONDS = 60 * 60


def _session_key(cafe):
    return f"customer:{cafe.pk}"


def current_customer(request, cafe):
    """The customer signed in to this café's site in this browser, or None."""
    customer_id = request.session.get(_session_key(cafe))
    if not customer_id:
        return None
    return Customer.objects.filter(pk=customer_id, cafe=cafe).first()


def log_in(request, customer):
    # A fresh session id on every sign in, so a session id seen before can't be reused.
    request.session.cycle_key()
    request.session[_session_key(customer.cafe)] = customer.pk
    customer.last_login_at = timezone.now()
    customer.save(update_fields=["last_login_at"])


def log_out(request, cafe):
    request.session.pop(_session_key(cafe), None)
    request.session.cycle_key()


def _form_key(request, cafe, form_name):
    raw = f"{form_name}|{cafe.pk}|{client_ip(request)}"
    return "form-use:" + hashlib.sha256(raw.encode()).hexdigest()


def too_many(request, cafe, form_name):
    return cache.get(_form_key(request, cafe, form_name), 0) >= FORM_LIMIT


def count_use(request, cafe, form_name):
    key = _form_key(request, cafe, form_name)
    if cache.add(key, 1, FORM_WINDOW_SECONDS):
        return
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, FORM_WINDOW_SECONDS)
