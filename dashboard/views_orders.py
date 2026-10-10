"""The staff side of online ordering: a live board of orders to make and hand over."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from operations.models import Sale
from ordering import services
from ordering.models import Order

from .access import cafe_access


def _board(cafe):
    today_start = cafe.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    active = list(
        Order.objects.filter(cafe=cafe, status__in=Order.ACTIVE).prefetch_related("lines").order_by("created_at")
    )
    columns = [
        (status, label, [o for o in active if o.status == status])
        for status, label in Order.Status.choices
        if status in Order.ACTIVE
    ]
    done = Order.objects.filter(
        cafe=cafe, status__in=[Order.Status.COLLECTED, Order.Status.CANCELLED], status_changed_at__gte=today_start
    ).order_by("-status_changed_at")[:10]
    return {
        "columns": columns,
        "done": done,
        "new_count": sum(o.status == Order.Status.NEW for o in active),
        "payment_methods": Sale.PaymentMethod.choices,
        "now": timezone.now(),
    }


@cafe_access()
def orders(request):
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/_orders_board.html", {**_board(request.cafe), "partial": True})
    return render(request, "dashboard/orders.html", _board(request.cafe))


@require_POST
@cafe_access()
def order_status(request, pk):
    order = get_object_or_404(Order, pk=pk, cafe=request.cafe)
    try:
        services.set_status(order, request.POST.get("status"), request.user, request.POST.get("payment_method", "cash"))
    except ValidationError as error:
        messages.error(request, error.messages[0])
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/_orders_board.html", {**_board(request.cafe), "partial": True})
    return redirect("dashboard:orders", cafe_slug=request.cafe.slug)
