"""Basket, pickup times, placing orders and moving them along. Views stay thin."""

import datetime as dt
import hashlib

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from cafes.models import MenuItem
from dashboard.throttle import client_ip
from operations.models import Sale, SaleLine

from .models import Order, OrderLine, Sugar, new_code

MAX_QUANTITY = 20
MAX_LINES = 30
NOTE_LENGTH = 140
SLOT_MINUTES = 15
FIRST_SLOT_AFTER = dt.timedelta(minutes=15)
ORDERS_PER_WINDOW = 5
ORDER_WINDOW_SECONDS = 15 * 60


# --- Basket (kept in the customer's session, never holds prices) -------------


class Basket:
    def __init__(self, request, cafe):
        self.session = request.session
        self.cafe = cafe
        self.key = f"basket:{cafe.pk}"

    @property
    def raw(self):
        return self.session.get(self.key, [])

    def _save(self, lines):
        self.session[self.key] = lines
        self.session.modified = True

    def add(self, item, quantity, sugar="", note=""):
        if item.category.cafe_id != self.cafe.pk:
            raise ValidationError("That item isn't on this café's menu.")
        if not item.is_available:
            raise ValidationError(f"Sorry, {item.name} is sold out.")
        if not 1 <= quantity <= MAX_QUANTITY:
            raise ValidationError(f"Choose between 1 and {MAX_QUANTITY}.")
        sugar = sugar if item.asks_sugar and sugar in Sugar.values else ""
        if item.asks_sugar and not sugar:
            raise ValidationError("Choose how much sugar you'd like.")
        note = " ".join(note.split())[:NOTE_LENGTH]
        lines = self.raw
        for line in lines:  # the same drink made the same way just goes up in number
            if (line["item"], line["sugar"], line["note"]) == (item.pk, sugar, note):
                line["qty"] = min(MAX_QUANTITY, line["qty"] + quantity)
                break
        else:
            if len(lines) >= MAX_LINES:
                raise ValidationError("Your basket is full.")
            lines.append({"item": item.pk, "qty": quantity, "sugar": sugar, "note": note})
        self._save(lines)

    def update(self, index, quantity):
        lines = self.raw
        if 0 <= index < len(lines):
            if quantity <= 0:
                lines.pop(index)
            else:
                lines[index]["qty"] = min(MAX_QUANTITY, quantity)
            self._save(lines)

    def clear(self):
        self.session.pop(self.key, None)

    def lines(self):
        """Basket lines with their menu items and current prices; items that left the menu drop out."""
        raw = self.raw
        items = MenuItem.objects.filter(category__cafe=self.cafe, pk__in={r["item"] for r in raw}).in_bulk()
        lines = []
        for index, r in enumerate(raw):
            item = items.get(r["item"])
            if item is None:
                continue
            lines.append(
                {
                    "index": index,
                    "item": item,
                    "quantity": r["qty"],
                    "sugar": r["sugar"],
                    "sugar_label": Sugar(r["sugar"]).label if r["sugar"] else "",
                    "note": r["note"],
                    "line_total": item.price * r["qty"],
                }
            )
        return lines

    def count(self):
        return sum(r["qty"] for r in self.raw)


def remember_order(request, order):
    request.session[f"order:{order.cafe_id}"] = str(order.token)


def latest_order(request, cafe):
    """The customer's most recent order here while it's still on its way, for the 'Your order' link."""
    token = request.session.get(f"order:{cafe.pk}")
    if not token:
        return None
    return Order.objects.filter(cafe=cafe, token=token, status__in=Order.ACTIVE).first()


# --- Pickup times ---------------------------------------------------------------


def _closing_time(cafe, day):
    hours = cafe.hours_for(day)
    if hours is None:
        return None, None
    opens = dt.datetime.combine(day, hours.opens, tzinfo=cafe.tz)
    closes = dt.datetime.combine(day, hours.closes, tzinfo=cafe.tz)
    if hours.crosses_midnight:
        closes += dt.timedelta(days=1)
    return opens, closes


def pickup_options(cafe, now=None):
    """
    (asap_available, [later slots]) for today. Slots are every 15 minutes while the café
    is open, starting 15 minutes from now, and the last one is 15 minutes before closing.
    """
    now = (now or timezone.now()).astimezone(cafe.tz)
    asap = cafe.is_open_at(now)
    opens, closes = _closing_time(cafe, now.date())
    slots = []
    if opens:
        start = max(opens, now + FIRST_SLOT_AFTER)
        # round up to the next quarter hour
        start += dt.timedelta(
            minutes=(-start.minute) % SLOT_MINUTES, seconds=-start.second, microseconds=-start.microsecond
        )
        slot = start
        while slot <= closes - dt.timedelta(minutes=SLOT_MINUTES):
            slots.append(slot)
            slot += dt.timedelta(minutes=SLOT_MINUTES)
    return asap, slots


def can_order(cafe, now=None):
    asap, slots = pickup_options(cafe, now)
    return cafe.accepts_orders and (asap or bool(slots))


# --- Placing an order -----------------------------------------------------------


def _throttle_key(request, cafe):
    return "orders:" + hashlib.sha256(f"{cafe.pk}|{client_ip(request)}".encode()).hexdigest()


def too_many_orders(request, cafe):
    return cache.get(_throttle_key(request, cafe), 0) >= ORDERS_PER_WINDOW


def _count_order(request, cafe):
    key = _throttle_key(request, cafe)
    if not cache.add(key, 1, ORDER_WINDOW_SECONDS):
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, ORDER_WINDOW_SECONDS)


def place_order(request, cafe, basket, name, phone, pickup):
    """
    Turn the basket into an order. `pickup` is "asap" or an ISO time from pickup_options.
    Prices come from the menu at this moment, never from the browser.
    """
    if not cafe.accepts_orders:
        raise ValidationError("This café isn't taking online orders right now.")
    if too_many_orders(request, cafe):
        raise ValidationError("You've placed several orders already. Please call the café if you need more.")
    lines = basket.lines()
    if not lines:
        raise ValidationError("Your basket is empty.")
    sold_out = [line["item"].name for line in lines if not line["item"].is_available]
    if sold_out:
        raise ValidationError(f"Sorry, {', '.join(sold_out)} just sold out. Please remove it to continue.")

    asap, slots = pickup_options(cafe)
    if pickup == "asap":
        if not asap:
            raise ValidationError("We're closed right now. Please choose a pickup time.")
        pickup_at = None
    else:
        pickup_at = next((s for s in slots if s.isoformat() == pickup), None)
        if pickup_at is None:
            raise ValidationError("Please choose one of the pickup times shown.")

    for _ in range(5):  # codes are random; retry on the rare clash
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    cafe=cafe,
                    code=new_code(),
                    customer_name=name,
                    customer_phone=phone,
                    pickup_at=pickup_at,
                    total=sum(line["line_total"] for line in lines),
                )
                OrderLine.objects.bulk_create(
                    OrderLine(
                        order=order,
                        menu_item=line["item"],
                        name=line["item"].name,
                        quantity=line["quantity"],
                        unit_price=line["item"].price,
                        unit_cost=line["item"].cost,
                        sugar=line["sugar"],
                        note=line["note"],
                    )
                    for line in lines
                )
            break
        except IntegrityError:
            continue
    else:
        raise ValidationError("Something went wrong. Please try again.")
    basket.clear()
    remember_order(request, order)
    _count_order(request, cafe)
    return order


# --- Staff moving an order along --------------------------------------------


NEXT_STATUS = {
    Order.Status.NEW: Order.Status.PREPARING,
    Order.Status.PREPARING: Order.Status.READY,
    Order.Status.READY: Order.Status.COLLECTED,
}


@transaction.atomic
def set_status(order, status, user, payment_method=Sale.PaymentMethod.CASH):
    """Move an order on. Collecting it records the sale so it shows in the reports."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if status == order.status:
        return order
    if status == Order.Status.CANCELLED:
        if not order.is_active:
            raise ValidationError("Only orders that haven't been collected can be cancelled.")
    elif NEXT_STATUS.get(order.status) != status and not (
        order.status == Order.Status.NEW and status == Order.Status.READY
    ):
        raise ValidationError("That order has already moved on. The screen has been refreshed.")
    if status == Order.Status.COLLECTED:
        if payment_method not in Sale.PaymentMethod.values:
            raise ValidationError("Choose how the customer paid.")
        sale = Sale.objects.create(cafe=order.cafe, recorded_by=user, payment_method=payment_method)
        SaleLine.objects.bulk_create(
            SaleLine(
                sale=sale,
                menu_item_id=line.menu_item_id,
                name=line.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                unit_cost=line.unit_cost,
            )
            for line in order.lines.all()
        )
        sale.recalculate()
        order.sale = sale
    order.status = status
    order.status_changed_at = timezone.now()
    order.save(update_fields=["status", "status_changed_at", "sale"])
    return order
