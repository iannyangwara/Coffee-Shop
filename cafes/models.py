"""
Core data for each café: its details, opening hours, menu and staff.

Every table here hangs off a Cafe, and every query the app makes is filtered
by café, so one café's data is never visible to another.
"""

import datetime as dt
import zoneinfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

# Paths a café slug may not take because the platform itself uses them.
RESERVED_SLUGS = {
    "admin",
    "dashboard",
    "static",
    "media",
    "accounts",
    "api",
    "www",
    "healthz",
    "login",
    "logout",
    "password",  # dashboard paths
}

hex_colour = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use a colour like #6b3e26.")


def validate_slug_not_reserved(value):
    if value in RESERVED_SLUGS:
        raise ValidationError("That web address is reserved. Please choose another.")


def validate_timezone(value):
    if value not in zoneinfo.available_timezones():
        raise ValidationError("Unknown timezone.")


def validate_image_size(image):
    if image and image.size > settings.MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError("Image is too large (max 5 MB).")


class Cafe(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(
        max_length=60,
        unique=True,
        validators=[validate_slug_not_reserved],
        help_text="Used in the web address, e.g. /bean-house/",
    )
    tagline = models.CharField(max_length=160, blank=True)
    about = models.TextField(blank=True)

    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(
        max_length=30, blank=True, help_text="Number in international format, e.g. 254712345678"
    )
    instagram = models.CharField(max_length=60, blank=True, help_text="Handle without the @")

    address = models.CharField(max_length=255, blank=True)
    town = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    timezone = models.CharField(max_length=64, default="Africa/Nairobi", validators=[validate_timezone])
    currency = models.CharField(max_length=3, default="USD", help_text="Three-letter code, e.g. USD")

    logo = models.ImageField(upload_to="logos/", blank=True, validators=[validate_image_size])
    cover_photo = models.ImageField(upload_to="covers/", blank=True, validators=[validate_image_size])
    brand_colour = models.CharField(max_length=7, default="#6b3e26", validators=[hex_colour])

    is_published = models.BooleanField(default=True, help_text="Unpublished cafés are hidden from the public.")
    accepts_orders = models.BooleanField(
        "take orders online",
        default=True,
        help_text="Customers can order from your website and pay when they collect.",
    )
    clock_in_radius_m = models.PositiveIntegerField(
        "clock-in distance (metres)",
        default=150,
        help_text="Staff clocking in further than this from the café's map pin are flagged for you to check.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("cafes:home", kwargs={"cafe_slug": self.slug})

    @property
    def cover_url(self):
        return self.cover_photo.url if self.cover_photo else static("cafes/stock/cover.svg")

    @property
    def tz(self):
        return zoneinfo.ZoneInfo(self.timezone)

    def local_now(self):
        return timezone.now().astimezone(self.tz)

    def hours_for(self, date):
        """The OpeningHours row for a date, or None if closed that day."""
        if self.closures.filter(date=date).exists():
            return None
        hours = next((h for h in self.opening_hours.all() if h.weekday == date.weekday()), None)
        if hours is None or hours.is_closed:
            return None
        return hours

    def is_open_at(self, moment):
        """Whether the café is open at an aware datetime (handles past-midnight closing)."""
        local = moment.astimezone(self.tz)
        today = local.date()
        hours = self.hours_for(today)
        if hours and hours.contains(local.time()):
            return True
        # A late-night shift that started yesterday may still be running.
        yesterday = self.hours_for(today - dt.timedelta(days=1))
        return bool(yesterday and yesterday.crosses_midnight and local.time() < yesterday.closes)

    def is_open_now(self):
        return self.is_open_at(timezone.now())

    @property
    def map_bbox(self):
        """Bounding box string for the OpenStreetMap embed, centred on the café."""
        if self.latitude is None or self.longitude is None:
            return ""
        lat, lon = float(self.latitude), float(self.longitude)
        return f"{lon - 0.006:.6f},{lat - 0.004:.6f},{lon + 0.006:.6f},{lat + 0.004:.6f}"

    def week_schedule(self):
        """Seven (day name, OpeningHours or None) pairs, Monday first."""
        by_day = {h.weekday: h for h in self.opening_hours.all()}
        return [(name, by_day.get(i)) for i, name in OpeningHours.Weekday.choices]


class OpeningHours(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="opening_hours")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    is_closed = models.BooleanField(default=False)
    opens = models.TimeField(null=True, blank=True)
    closes = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["weekday"]
        constraints = [
            models.UniqueConstraint(fields=["cafe", "weekday"], name="one_hours_row_per_day"),
            models.CheckConstraint(
                condition=models.Q(is_closed=True) | (models.Q(opens__isnull=False) & models.Q(closes__isnull=False)),
                name="open_days_have_times",
            ),
        ]
        verbose_name_plural = "opening hours"

    def __str__(self):
        if self.is_closed:
            return f"{self.get_weekday_display()}: closed"
        return f"{self.get_weekday_display()}: {self.opens:%H:%M}–{self.closes:%H:%M}"

    def clean(self):
        if not self.is_closed:
            if self.opens is None or self.closes is None:
                raise ValidationError("Set both opening and closing times, or mark the day closed.")
            if self.opens == self.closes:
                raise ValidationError("Opening and closing times can't be the same.")

    @property
    def crosses_midnight(self):
        return not self.is_closed and self.closes < self.opens

    def contains(self, t):
        if self.is_closed:
            return False
        if self.crosses_midnight:
            return t >= self.opens
        return self.opens <= t < self.closes


class Closure(models.Model):
    """A one-off day the café is closed (public holiday, staff training...)."""

    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="closures")
    date = models.DateField()
    note = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["cafe", "date"], name="one_closure_per_day")]

    def __str__(self):
        return f"{self.cafe} closed {self.date}"


class MenuCategory(models.Model):
    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="menu_categories")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        verbose_name_plural = "menu categories"
        constraints = [models.UniqueConstraint(fields=["cafe", "name"], name="unique_category_name_per_cafe")]

    def __str__(self):
        return self.name


class StockImage(models.TextChoices):
    """Built-in pictures (static/cafes/stock/) for cafés that don't have their own photos yet."""

    ESPRESSO = "espresso", "Espresso"
    CAPPUCCINO = "cappuccino", "Cappuccino"
    LATTE = "latte", "Latte"
    CHAI = "chai", "Chai / tea"
    HOT_CHOCOLATE = "hot-chocolate", "Hot chocolate"
    ICED_LATTE = "iced-latte", "Iced coffee"
    JUICE = "juice", "Juice"
    CROISSANT = "croissant", "Croissant"
    BANANA_BREAD = "banana-bread", "Cake / loaf slice"
    MANDAZI = "mandazi", "Mandazi / pastries"
    BREAKFAST = "breakfast", "Full breakfast"
    AVOCADO_TOAST = "avocado-toast", "Avocado toast"


class MenuItem(models.Model):
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cost = models.DecimalField(
        "cost to make",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Ingredients and packaging for one. Used to work out your profit; never shown to customers.",
    )
    photo = models.ImageField(upload_to="menu/", blank=True, validators=[validate_image_size])
    stock_image = models.CharField(
        "built-in picture",
        max_length=30,
        choices=StockImage.choices,
        blank=True,
        help_text="Shown when there's no uploaded photo.",
    )
    is_available = models.BooleanField(default=True, help_text="Untick when sold out; it stays on the menu greyed out.")
    is_featured = models.BooleanField(default=False, help_text="Shown on the café's home page.")
    is_vegetarian = models.BooleanField(default=False)
    asks_sugar = models.BooleanField(
        "offer a sugar choice",
        default=False,
        help_text="Customers ordering online pick no sugar, less, normal or extra.",
    )
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name

    @property
    def cafe(self):
        return self.category.cafe

    @property
    def image_url(self):
        """The uploaded photo if there is one, else the chosen built-in picture, else nothing."""
        if self.photo:
            return self.photo.url
        if self.stock_image:
            return static(f"cafes/stock/{self.stock_image}.svg")
        return ""


class StaffMembership(models.Model):
    """Links a login to a café. Owners can change café settings; staff can manage the menu and hours."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        STAFF = "staff", "Staff"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    cafe = models.ForeignKey(Cafe, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "cafe"], name="one_membership_per_user_cafe")]

    def __str__(self):
        return f"{self.user} – {self.cafe} ({self.get_role_display()})"

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER
