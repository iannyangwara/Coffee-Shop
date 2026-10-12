"""
Orders customers place on a café's website and pay for when they collect.

Like sale lines, order lines copy the item's name, price and cost when the
order is placed, so later menu changes never rewrite an order. When staff mark
an order collected it is recorded as a Sale, so it counts in the reports.
"""

import secrets
import uuid
from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from cafes.models import Cafe, MenuItem
from operations.models import Sale

# No 0/O or 1/I, so a code read out at the counter can't be misheard.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(4))


class Sugar(models.TextChoices):
    NONE = "none", "No sugar"
    LESS = "less", "Less sugar"
    NORMAL = "normal", "Normal sugar"
    EXTRA = "extra", "Extra sugar"


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Received"
        PREPARING = "preparing", "Being made"
        READY = "ready", "Ready to collect"
        COLLECTED = "collected", "Collected"
        CANCELLED = "cancelled", "Cancelled"

    ACTIVE = (Status.NEW, Status.PREPARING, Status.READY)

    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="orders")
    code = models.CharField(max_length=6, default=new_code, help_text="Short code the customer gives at the counter.")
    token = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, help_text="Secret part of the tracking link."
    )
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    customer_name = models.CharField(max_length=80)
    customer_phone = models.CharField(max_length=30)
    pickup_at = models.DateTimeField(null=True, blank=True, help_text="Empty means as soon as possible.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status_changed_at = models.DateTimeField(auto_now_add=True)
    sale = models.OneToOneField(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name="order")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["cafe", "code"], name="unique_order_code_per_cafe")]

    def __str__(self):
        return f"Order {self.code} at {self.cafe}"

    @property
    def is_active(self):
        return self.status in self.ACTIVE

    @property
    def step(self):
        """Position on the received → being made → ready progress bar (0–3)."""
        return {self.Status.NEW: 1, self.Status.PREPARING: 2, self.Status.READY: 3, self.Status.COLLECTED: 3}.get(
            self.status, 0
        )


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(99)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sugar = models.CharField(max_length=10, choices=Sugar.choices, blank=True)
    note = models.CharField("special request", max_length=140, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} × {self.name}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity
