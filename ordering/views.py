"""The customer side of ordering: item details, the basket, checkout and order tracking."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cafes.models import MenuItem
from cafes.views import _base_context, _published_cafe

from . import services
from .forms import AddToBasketForm, CheckoutForm
from .models import Order


def item_detail(request, cafe_slug, item_id):
    cafe = _published_cafe(cafe_slug)
    item = get_object_or_404(MenuItem.objects.select_related("category"), pk=item_id, category__cafe=cafe)
    form = AddToBasketForm(request.POST or None, item=item)
    ordering = services.can_order(cafe)
    if request.method == "POST" and form.is_valid():
        basket = services.Basket(request, cafe)
        try:
            if not ordering:
                raise ValidationError("Online ordering isn't open right now.")
            basket.add(
                item, form.cleaned_data["quantity"], form.cleaned_data.get("sugar", ""), form.cleaned_data["note"]
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, f"Added {item.name} to your order.")
            return redirect("cafes:menu", cafe_slug=cafe.slug)
    more = (
        MenuItem.objects.filter(category=item.category, is_available=True).exclude(pk=item.pk).order_by("position")[:3]
    )
    return render(
        request,
        "cafes/item_detail.html",
        {**_base_context(request, cafe), "item": item, "form": form, "ordering": ordering, "more": more},
    )


def basket(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    basket = services.Basket(request, cafe)
    asap, slots = services.pickup_options(cafe)
    form = CheckoutForm(request.POST or None, asap=asap, slots=slots)
    if request.method == "POST" and form.is_valid():
        try:
            order = services.place_order(
                request,
                cafe,
                basket,
                form.cleaned_data["name"],
                form.cleaned_data["phone"],
                form.cleaned_data["pickup"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect("cafes:order_status", cafe_slug=cafe.slug, token=order.token)
    lines = basket.lines()
    return render(
        request,
        "cafes/basket.html",
        {
            **_base_context(request, cafe),
            "lines": lines,
            "total": sum(line["line_total"] for line in lines),
            "form": form,
            "ordering": services.can_order(cafe),
        },
    )


@require_POST
def basket_update(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    try:
        index, quantity = int(request.POST["index"]), int(request.POST["quantity"])
    except (KeyError, ValueError):
        return redirect("cafes:basket", cafe_slug=cafe.slug)
    services.Basket(request, cafe).update(index, quantity)
    return redirect("cafes:basket", cafe_slug=cafe.slug)


def order_status(request, cafe_slug, token):
    cafe = _published_cafe(cafe_slug)
    order = get_object_or_404(Order.objects.prefetch_related("lines"), cafe=cafe, token=token)
    template = "cafes/_order_progress.html" if request.headers.get("HX-Request") else "cafes/order_status.html"
    with timezone.override(cafe.tz):
        return render(request, template, {**_base_context(request, cafe), "order": order})
