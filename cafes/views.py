from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, render

from customers.services import current_customer
from ordering.services import Basket, latest_order

from .models import Cafe, MenuCategory, MenuItem


def platform_home(request):
    cafes = Cafe.objects.filter(is_published=True).only("name", "slug", "tagline", "town", "accepts_orders")
    return render(request, "cafes/platform_home.html", {"cafes": cafes})


def _published_cafe(slug):
    return get_object_or_404(Cafe.objects.prefetch_related("opening_hours", "closures"), slug=slug, is_published=True)


def _base_context(request, cafe):
    today = cafe.local_now().date()
    return {
        "cafe": cafe,
        "is_open": cafe.is_open_now(),
        "today_hours": cafe.hours_for(today),
        "basket_count": Basket(request, cafe).count(),
        "my_order": latest_order(request, cafe),
        "customer": current_customer(request, cafe),
    }


def cafe_home(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    items = MenuItem.objects.filter(category__cafe=cafe).order_by("category__position", "position")
    featured = items.filter(is_featured=True)[:6]
    # A few pictures of things that aren't already in the favourites, for the visit and gallery sections.
    gallery = [i for i in items.filter(is_featured=False) if i.image_url][:4]
    categories = list(cafe.menu_categories.filter(items__isnull=False).distinct().values_list("name", flat=True))
    context = {**_base_context(request, cafe), "featured": featured, "gallery": gallery, "categories": categories}
    return render(request, "cafes/home.html", context)


def cafe_menu(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    query = " ".join(request.GET.get("q", "").split())[:60]
    items = MenuItem.objects.order_by("position", "id")
    for word in query.split():
        # Every word has to match somewhere: "iced latte" finds the iced latte, not every latte.
        items = items.filter(
            Q(name__icontains=word) | Q(description__icontains=word) | Q(category__name__icontains=word)
        )
    categories = MenuCategory.objects.filter(cafe=cafe).prefetch_related(Prefetch("items", queryset=items))
    categories = [c for c in categories if c.items.all()]
    context = {
        **_base_context(request, cafe),
        "categories": categories,
        "query": query,
        "result_count": sum(len(c.items.all()) for c in categories),
    }
    return render(request, "cafes/menu.html", context)


def cafe_visit(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    today = cafe.local_now().date()
    upcoming_closures = cafe.closures.filter(date__gte=today)[:5]
    return render(
        request,
        "cafes/visit.html",
        {
            **_base_context(request, cafe),
            "schedule": cafe.week_schedule(),
            "today_weekday": today.weekday(),
            "upcoming_closures": upcoming_closures,
        },
    )
