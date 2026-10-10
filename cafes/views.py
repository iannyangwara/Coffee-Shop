from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from .models import Cafe, MenuCategory, MenuItem


def platform_home(request):
    cafes = Cafe.objects.filter(is_published=True).only("name", "slug", "tagline", "town")
    return render(request, "cafes/platform_home.html", {"cafes": cafes})


def _published_cafe(slug):
    return get_object_or_404(Cafe.objects.prefetch_related("opening_hours", "closures"), slug=slug, is_published=True)


def _base_context(cafe):
    today = cafe.local_now().date()
    return {"cafe": cafe, "is_open": cafe.is_open_now(), "today_hours": cafe.hours_for(today)}


def cafe_home(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    featured = (
        MenuItem.objects.filter(category__cafe=cafe, is_featured=True)
        .select_related("category")
        .order_by("category__position", "position")[:6]
    )
    return render(request, "cafes/home.html", {**_base_context(cafe), "featured": featured})


def cafe_menu(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    categories = MenuCategory.objects.filter(cafe=cafe).prefetch_related(
        Prefetch("items", queryset=MenuItem.objects.order_by("position", "id"))
    )
    categories = [c for c in categories if c.items.all()]
    return render(request, "cafes/menu.html", {**_base_context(cafe), "categories": categories})


def cafe_visit(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    today = cafe.local_now().date()
    upcoming_closures = cafe.closures.filter(date__gte=today)[:5]
    return render(
        request,
        "cafes/visit.html",
        {
            **_base_context(cafe),
            "schedule": cafe.week_schedule(),
            "today_weekday": today.weekday(),
            "upcoming_closures": upcoming_closures,
        },
    )
