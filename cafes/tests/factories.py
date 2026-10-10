"""Small helpers to build test data without repeating boilerplate."""

import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model

from cafes.models import Cafe, MenuCategory, MenuItem, OpeningHours, StaffMembership

PASSWORD = "correct-horse-battery-staple"


def make_cafe(slug="bean-house", **kwargs):
    defaults = {"name": slug.replace("-", " ").title(), "timezone": "Africa/Nairobi"}
    return Cafe.objects.create(slug=slug, **(defaults | kwargs))


def set_hours(cafe, opens=dt.time(7), closes=dt.time(19), days=range(7)):
    for day in days:
        OpeningHours.objects.update_or_create(
            cafe=cafe, weekday=day, defaults={"opens": opens, "closes": closes, "is_closed": False}
        )


def make_item(cafe, name="Cappuccino", price="250", category_name="Hot drinks", **kwargs):
    category, _ = MenuCategory.objects.get_or_create(cafe=cafe, name=category_name)
    return MenuItem.objects.create(category=category, name=name, price=Decimal(price), **kwargs)


def make_user(username, cafe=None, role=StaffMembership.Role.OWNER):
    user = get_user_model().objects.create_user(username, password=PASSWORD)
    if cafe:
        StaffMembership.objects.create(user=user, cafe=cafe, role=role)
    return user
