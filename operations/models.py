"""
Day-to-day running of a café: sales rung up at the counter and staff shifts.

Like everything else, every row belongs to one café. Sale lines copy the
item's name, price and cost at the moment of sale, so later menu changes
never rewrite past figures.
"""

import math
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q, Sum
from django.utils import timezone

from cafes.models import Cafe, MenuItem


class SaleQuerySet(models.QuerySet):
    def valid(self):
        return self.filter(voided_at__isnull=True)


class Sale(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE = "mobile", "Mobile money"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="sales")
    sold_at = models.DateTimeField(default=timezone.now, db_index=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    cost_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"), help_text="Sum of known item costs."
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    objects = SaleQuerySet.as_manager()

    class Meta:
        ordering = ["-sold_at"]
        indexes = [models.Index(fields=["cafe", "sold_at"])]

    def __str__(self):
        return f"Sale {self.pk} at {self.cafe}"

    @property
    def is_void(self):
        return self.voided_at is not None

    def recalculate(self):
        totals = self.lines.aggregate(
            total=Sum(F("unit_price") * F("quantity")),
            cost=Sum(F("unit_cost") * F("quantity"), filter=Q(unit_cost__isnull=False)),
        )
        self.total = totals["total"] or Decimal("0")
        self.cost_total = totals["cost"] or Decimal("0")
        self.save(update_fields=["total", "cost_total"])


class SaleLine(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.quantity} × {self.name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


def distance_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in metres between two points."""
    r = 6_371_000
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = p2 - p1
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Shift(models.Model):
    """One worker's time at the café, with where they were when they clocked in and out."""

    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="shifts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shifts")

    clock_in_at = models.DateTimeField(default=timezone.now)
    clock_in_lat = models.DecimalField(max_digits=9, decimal_places=6)
    clock_in_lng = models.DecimalField(max_digits=9, decimal_places=6)
    clock_in_accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    clock_in_distance_m = models.PositiveIntegerField(null=True, blank=True)

    clock_out_at = models.DateTimeField(null=True, blank=True)
    clock_out_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    clock_out_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    clock_out_accuracy_m = models.PositiveIntegerField(null=True, blank=True)
    clock_out_distance_m = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-clock_in_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cafe", "user"], condition=Q(clock_out_at__isnull=True), name="one_open_shift_per_worker"
            ),
            models.CheckConstraint(
                condition=Q(clock_out_at__isnull=True) | Q(clock_out_at__gte=F("clock_in_at")),
                name="shift_ends_after_it_starts",
            ),
        ]

    def __str__(self):
        return f"{self.user} at {self.cafe} from {self.clock_in_at:%Y-%m-%d %H:%M}"

    @property
    def is_open(self):
        return self.clock_out_at is None

    @property
    def duration(self):
        return (self.clock_out_at or timezone.now()) - self.clock_in_at

    @property
    def hours(self):
        return self.duration.total_seconds() / 3600

    def _outside(self, distance):
        return distance is not None and distance > self.cafe.clock_in_radius_m

    @property
    def clock_in_outside(self):
        return self._outside(self.clock_in_distance_m)

    @property
    def clock_out_outside(self):
        return self._outside(self.clock_out_distance_m)

    @property
    def flagged(self):
        return self.clock_in_outside or self.clock_out_outside
