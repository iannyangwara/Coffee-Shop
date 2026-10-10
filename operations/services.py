"""The few actions that change sales and shift records, kept in one place so views stay thin."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from cafes.models import MenuItem

from .models import Sale, SaleLine, Shift, distance_m

MAX_QUANTITY = 99


@transaction.atomic
def record_sale(cafe, user, quantities, payment_method):
    """
    Ring up a sale. `quantities` maps menu item id -> how many.

    Prices and costs always come from the database, never from the browser.
    """
    if payment_method not in Sale.PaymentMethod.values:
        raise ValidationError("Choose how the customer paid.")
    wanted = {int(pk): int(qty) for pk, qty in quantities.items() if int(qty) > 0}
    if not wanted:
        raise ValidationError("Add at least one item.")
    if any(qty > MAX_QUANTITY for qty in wanted.values()):
        raise ValidationError(f"That's a lot! Up to {MAX_QUANTITY} of one item per sale.")
    items = MenuItem.objects.filter(category__cafe=cafe, pk__in=wanted)
    if len(items) != len(wanted):
        raise ValidationError("Some items aren't on this café's menu.")
    sale = Sale.objects.create(cafe=cafe, recorded_by=user, payment_method=payment_method)
    SaleLine.objects.bulk_create(
        SaleLine(
            sale=sale,
            menu_item=item,
            name=item.name,
            quantity=wanted[item.pk],
            unit_price=item.price,
            unit_cost=item.cost,
        )
        for item in items
    )
    sale.recalculate()
    return sale


def void_sale(sale, user):
    if sale.is_void:
        return
    sale.voided_at = timezone.now()
    sale.voided_by = user
    sale.save(update_fields=["voided_at", "voided_by"])


def open_shift(cafe, user):
    return Shift.objects.filter(cafe=cafe, user=user, clock_out_at__isnull=True).first()


def _location(cafe, lat, lng, accuracy):
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        raise ValidationError("We couldn't get your location. Allow location access and try again.") from None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValidationError("That location doesn't look right. Please try again.")
    try:
        accuracy = max(0, round(float(accuracy))) if accuracy not in (None, "") else None
    except ValueError:
        accuracy = None
    distance = None
    if cafe.latitude is not None and cafe.longitude is not None:
        distance = round(distance_m(lat, lng, cafe.latitude, cafe.longitude))
    return round(lat, 6), round(lng, 6), accuracy, distance


def clock_in(cafe, user, lat, lng, accuracy=None):
    if open_shift(cafe, user):
        raise ValidationError("You're already clocked in.")
    lat, lng, accuracy, distance = _location(cafe, lat, lng, accuracy)
    try:
        with transaction.atomic():
            return Shift.objects.create(
                cafe=cafe,
                user=user,
                clock_in_lat=lat,
                clock_in_lng=lng,
                clock_in_accuracy_m=accuracy,
                clock_in_distance_m=distance,
            )
    except IntegrityError:  # double tap: another request opened the shift first
        raise ValidationError("You're already clocked in.") from None


def clock_out(cafe, user, lat, lng, accuracy=None):
    shift = open_shift(cafe, user)
    if shift is None:
        raise ValidationError("You're not clocked in.")
    lat, lng, accuracy, distance = _location(cafe, lat, lng, accuracy)
    shift.clock_out_at = timezone.now()
    shift.clock_out_lat, shift.clock_out_lng = lat, lng
    shift.clock_out_accuracy_m, shift.clock_out_distance_m = accuracy, distance
    shift.save()
    return shift
