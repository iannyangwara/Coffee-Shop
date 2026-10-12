"""
Customers who sign up on a café's website, and the messages people send a café.

Customer accounts belong to one café and are kept apart from staff logins on
purpose: a customer password can never open the dashboard, and a customer of
one café is a stranger to every other café on the platform.
"""

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models.functions import Lower

from cafes.models import Cafe


class Customer(models.Model):
    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField(max_length=80)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    password = models.CharField(max_length=128)
    wants_news = models.BooleanField(
        "happy to hear about offers", default=False, help_text="The customer agreed to hear about news and offers."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint("cafe", Lower("email"), name="one_customer_per_email_per_cafe"),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        def upgrade(raw):
            self.set_password(raw)
            self.save(update_fields=["password"])

        return check_password(raw_password, self.password, setter=upgrade)


class Enquiry(models.Model):
    """A question, complaint or compliment sent through the café's contact page."""

    class Kind(models.TextChoices):
        QUESTION = "question", "Question"
        COMPLAINT = "complaint", "Complaint"
        FEEDBACK = "feedback", "Compliment or feedback"

    class Status(models.TextChoices):
        NEW = "new", "New"
        RESOLVED = "resolved", "Dealt with"

    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="enquiries")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="enquiries")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.QUESTION)
    name = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    order_code = models.CharField(max_length=6, blank=True, help_text="Order code, if it's about an order.")
    message = models.TextField(max_length=2000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)
    staff_note = models.CharField("what we did", max_length=500, blank=True, help_text="Only your team sees this.")
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.get_kind_display()} from {self.name} at {self.cafe}"
