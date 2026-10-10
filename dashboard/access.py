"""Who may see which café's dashboard."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone

from cafes.models import Cafe, StaffMembership


def cafe_access(owner_only=False):
    """
    Resolve the café in the URL and check the logged-in user works there.

    Sets request.cafe and request.membership. Users with no link to the café
    get a 404 (not 403) so they can't even tell whether it exists.
    Platform superusers may manage any café as an owner. Times render in the café's timezone.
    """

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, cafe_slug, *args, **kwargs):
            cafe = get_object_or_404(Cafe, slug=cafe_slug)
            membership = StaffMembership.objects.filter(user=request.user, cafe=cafe).first()
            if membership is None:
                if not request.user.is_superuser:
                    raise Http404
                membership = StaffMembership(user=request.user, cafe=cafe, role=StaffMembership.Role.OWNER)
            if owner_only and not membership.is_owner:
                raise PermissionDenied
            request.cafe = cafe
            request.membership = membership
            # Show every time on the page in the café's own timezone, not the server's (UTC).
            with timezone.override(cafe.tz):
                return view(request, *args, **kwargs)

        return wrapper

    return decorator
