"""Create a realistic demo café so there's something to show and click around."""

import datetime as dt
import os
import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from cafes.models import Cafe, MenuCategory, MenuItem, OpeningHours, StaffMembership
from customers.models import Enquiry
from operations.models import Sale, SaleLine, Shift, distance_m

MENU = {
    "Hot drinks": [
        ("Espresso", "Single shot of our house roast.", "2.50", True, "espresso"),
        ("Cappuccino", "Espresso, steamed milk and a thick layer of foam.", "3.50", True, "cappuccino"),
        ("Café latte", "Smooth and milky.", "3.75", False, "latte"),
        ("Chai tea", "Strong black tea brewed with milk and spices.", "2.00", False, "chai"),
        ("Hot chocolate", "Rich cocoa with steamed milk.", "3.75", False, "hot-chocolate"),
    ],
    "Cold drinks": [
        ("Iced latte", "Espresso over ice with cold milk.", "4.25", False, "iced-latte"),
        ("Fresh passion juice", "Squeezed every morning.", "3.00", False, "juice"),
    ],
    "Bakery": [
        ("Butter croissant", "Baked in-house every morning.", "2.75", True, "croissant"),
        ("Banana bread", "Moist slice with walnuts.", "3.00", False, "banana-bread"),
        ("Mandazi (3 pcs)", "Lightly sweet East African doughnuts.", "2.00", False, "mandazi"),
    ],
    "Breakfast": [
        ("Full breakfast", "Eggs, sausage, toast, beans and grilled tomato.", "9.50", False, "breakfast"),
        ("Avocado toast", "Smashed avocado on sourdough with chilli flakes.", "7.00", True, "avocado-toast"),
    ],
}

# Rough cost to make one of each demo item, so the demo shows profit.
COSTS = {
    "Espresso": "0.55",
    "Cappuccino": "0.90",
    "Café latte": "1.00",
    "Chai tea": "0.40",
    "Hot chocolate": "1.10",
    "Iced latte": "1.20",
    "Fresh passion juice": "0.95",
    "Butter croissant": "0.85",
    "Banana bread": "0.70",
    "Mandazi (3 pcs)": "0.45",
    "Full breakfast": "3.60",
    "Avocado toast": "2.40",
}
# Drinks that ask the customer how much sugar they want when ordering online.
SUGAR_CHOICE = {"Espresso", "Cappuccino", "Café latte", "Chai tea", "Hot chocolate", "Iced latte"}
# How often each demo item is ordered, relative to the others.
POPULARITY = {
    "Cappuccino": 10,
    "Café latte": 8,
    "Chai tea": 7,
    "Espresso": 5,
    "Butter croissant": 6,
    "Mandazi (3 pcs)": 5,
    "Iced latte": 4,
    "Banana bread": 3,
    "Avocado toast": 3,
    "Fresh passion juice": 3,
    "Hot chocolate": 2,
    "Full breakfast": 2,
}
# Orders per hour of the day, relative: a breakfast rush and a smaller lunch one.
HOURLY = {7: 6, 8: 10, 9: 8, 10: 5, 11: 4, 12: 6, 13: 6, 14: 3, 15: 3, 16: 3, 17: 2, 18: 1}
DEMO_DAYS = 30

# Made-up details only: these cafés are for showing the platform, so nothing here
# should look like a real business, number or address.
DEMO_CAFES = {
    "bean-house": dict(
        name="Bean House",
        tagline="Fresh coffee and home baking in the heart of town",
        about=(
            "Bean House is a demo café showing what your own website could look like: "
            "your menu with prices and pictures, your hours, where to find you, and online ordering.\n\n"
            "Everything on this page is made up."
        ),
        phone="123456789",
        whatsapp="",
        email="hello@example.com",
        instagram="",
        address="12 Sample Street",
        town="Lisbon",
        latitude=Decimal("38.710700"),
        longitude=Decimal("-9.137500"),
        timezone="Europe/Lisbon",
    ),
    "hilltop-coffee": dict(
        name="Hilltop Coffee",
        tagline="See our menu and prices, then come and find us",
        about=(
            "Hilltop Coffee is a demo of a menu-only website: customers can browse the menu and prices, "
            "check the opening hours and find the café on the map, without ordering online.\n\n"
            "Everything on this page is made up."
        ),
        phone="123456789",
        whatsapp="",
        email="hello@example.com",
        instagram="",
        address="45 Example Road",
        town="Lisbon",
        latitude=Decimal("38.711800"),
        longitude=Decimal("-9.130100"),
        timezone="Europe/Lisbon",
        accepts_orders=False,
        brand_colour="#2f5d50",
        stock_cover="terrace",
    ),
}
# Phone number the first version of the demo was seeded with; see _replace_old_contact_details.
OLD_DEMO_PHONE = "+254 712 345 678"
# Where earlier versions of the demo put their map pins; see _move_to_new_location.
OLD_DEMO_PINS = {
    "bean-house": (Decimal("-0.420130"), Decimal("36.947600")),
    "hilltop-coffee": (Decimal("-0.423900"), Decimal("36.951200")),
}


class Command(BaseCommand):
    help = "Create the 'Bean House' demo café with a menu, hours and an owner login."

    def add_arguments(self, parser):
        parser.add_argument("--owner-username", default="demo-owner")
        parser.add_argument(
            "--owner-password",
            default=os.environ.get("DEMO_OWNER_PASSWORD"),
            help="Defaults to $DEMO_OWNER_PASSWORD. Required when the owner login doesn't exist yet.",
        )

    @transaction.atomic
    def handle(self, *args, owner_username, owner_password, **options):
        User = get_user_model()
        user = User.objects.filter(username=owner_username).first()
        if user is None and owner_password:
            user = User.objects.create_user(owner_username, password=owner_password, first_name="Demo")
            self.stdout.write(self.style.SUCCESS(f"Created owner login '{owner_username}'."))

        for slug, details in DEMO_CAFES.items():
            cafe = self._demo_cafe(slug, details)
            if user is None:
                continue
            StaffMembership.objects.get_or_create(user=user, cafe=cafe, defaults={"role": StaffMembership.Role.OWNER})
            self._add_missing_costs(cafe)
            self._offer_sugar_choice(cafe)
            if not Sale.objects.filter(cafe=cafe).exists():
                self._add_demo_sales(cafe, user)
        if user is None:
            self.stderr.write("No owner login created: pass --owner-password or set DEMO_OWNER_PASSWORD.")
            return
        bean_house = Cafe.objects.get(slug="bean-house")
        self._add_demo_barista(bean_house)
        if not bean_house.enquiries.exists():
            self._add_demo_messages(bean_house)

    def _demo_cafe(self, slug, details):
        cafe, created = Cafe.objects.get_or_create(slug=slug, defaults=details)
        if not created:
            self._replace_old_contact_details(cafe, details)
            self._move_to_new_location(cafe, details)
            self._add_missing_pictures(cafe)
            return cafe
        for day in OpeningHours.Weekday.values:
            if day == OpeningHours.Weekday.SUNDAY:
                OpeningHours.objects.create(cafe=cafe, weekday=day, opens=dt.time(9), closes=dt.time(14))
            else:
                OpeningHours.objects.create(cafe=cafe, weekday=day, opens=dt.time(7), closes=dt.time(19))
        for position, (category_name, items) in enumerate(MENU.items()):
            category = MenuCategory.objects.create(cafe=cafe, name=category_name, position=position)
            for item_position, (name, description, price, featured, picture) in enumerate(items):
                MenuItem.objects.create(
                    category=category,
                    name=name,
                    description=description,
                    price=Decimal(price),
                    is_featured=featured,
                    stock_image=picture,
                    asks_sugar=name in SUGAR_CHOICE,
                    position=item_position,
                )
        self.stdout.write(self.style.SUCCESS(f"Created demo café at {cafe.get_absolute_url()}"))
        return cafe

    def _move_to_new_location(self, cafe, details):
        """
        Move a demo café from its old map pin to the current one, only while it's still on the
        old pin. Past sales and shifts keep the same local clock times in the new timezone, and
        demo shift locations move with the café so they stay next to it on the map.
        """
        if (cafe.latitude, cafe.longitude) != OLD_DEMO_PINS.get(cafe.slug):
            return
        now = timezone.now()
        old_offset = now.astimezone(cafe.tz).utcoffset()
        dlat = details["latitude"] - cafe.latitude
        dlng = details["longitude"] - cafe.longitude
        for field in ["latitude", "longitude", "timezone", "town"]:
            setattr(cafe, field, details[field])
        cafe.save()
        shift = old_offset - now.astimezone(cafe.tz).utcoffset()
        Sale.objects.filter(cafe=cafe).update(sold_at=F("sold_at") + shift)
        Shift.objects.filter(cafe=cafe).update(
            clock_in_at=F("clock_in_at") + shift,
            clock_out_at=F("clock_out_at") + shift,
            clock_in_lat=F("clock_in_lat") + dlat,
            clock_in_lng=F("clock_in_lng") + dlng,
            clock_out_lat=F("clock_out_lat") + dlat,
            clock_out_lng=F("clock_out_lng") + dlng,
        )
        # Nothing may end up in the future after the move.
        Sale.objects.filter(cafe=cafe, sold_at__gt=now).update(sold_at=now)
        Shift.objects.filter(cafe=cafe, clock_out_at__gt=now).update(clock_out_at=now)
        Shift.objects.filter(cafe=cafe, clock_in_at__gt=now).update(clock_in_at=now)
        self.stdout.write(f"Moved {cafe.name} to {cafe.town}.")

    def _replace_old_contact_details(self, cafe, details):
        """
        The first demo café was seeded with realistic-looking contact details. Swap them for
        obviously made-up ones, but only while they're still the originals, so an owner's own
        edits are never overwritten.
        """
        if cafe.phone != OLD_DEMO_PHONE:
            return
        for field in ["tagline", "about", "phone", "whatsapp", "email", "instagram", "address", "town"]:
            setattr(cafe, field, details[field])
        cafe.save()
        self.stdout.write(f"Replaced {cafe.name}'s contact details with made-up demo ones.")

    def _add_missing_pictures(self, cafe):
        """Give demo items created before pictures existed their built-in picture (never overrides a choice)."""
        pictures = {name: picture for items in MENU.values() for name, *_, picture in items}
        updated = 0
        for item in MenuItem.objects.filter(category__cafe=cafe, stock_image="", photo=""):
            if item.name in pictures:
                item.stock_image = pictures[item.name]
                item.save(update_fields=["stock_image", "updated_at"])
                updated += 1
        if updated:
            self.stdout.write(f"Added pictures to {updated} demo menu items.")

    def _add_missing_costs(self, cafe):
        """Give demo items a cost to make (never overrides one the owner entered)."""
        updated = 0
        for item in MenuItem.objects.filter(category__cafe=cafe, cost__isnull=True, name__in=COSTS):
            item.cost = Decimal(COSTS[item.name])
            item.save(update_fields=["cost", "updated_at"])
            updated += 1
        if updated:
            self.stdout.write(f"Added costs to {updated} demo menu items.")

    def _offer_sugar_choice(self, cafe):
        """Turn on the sugar choice for demo drinks, once (an owner who later turns it off keeps it off)."""
        items = MenuItem.objects.filter(category__cafe=cafe)
        if items.filter(asks_sugar=True).exists():
            return
        updated = items.filter(name__in=SUGAR_CHOICE).update(asks_sugar=True)
        if updated:
            self.stdout.write(f"Turned on the sugar choice for {updated} demo drinks.")

    def _add_demo_sales(self, cafe, user):
        """A month of believable sales so the reports have something to show. Only runs on an empty till."""
        items = [i for i in MenuItem.objects.filter(category__cafe=cafe) if i.name in POPULARITY]
        if not items:
            return
        rng = random.Random(2026)
        weights = [POPULARITY[i.name] for i in items]
        today = cafe.local_now().date()
        now = cafe.local_now()
        methods, method_weights = ["mobile", "cash", "card"], [6, 3, 1]
        planned = []
        for days_ago in range(DEMO_DAYS - 1, -1, -1):
            day = today - dt.timedelta(days=days_ago)
            hours = cafe.hours_for(day)
            if hours is None:
                continue
            busy = 1.3 if day.weekday() in (4, 5) else 1.0  # Fridays and Saturdays are busier
            for hour, weight in HOURLY.items():
                if not hours.contains(dt.time(hour)):
                    continue
                for _ in range(round(weight * busy * rng.uniform(0.6, 1.4))):
                    moment = dt.datetime.combine(day, dt.time(hour, rng.randrange(60)), tzinfo=cafe.tz)
                    if moment >= now:
                        continue
                    picks = rng.choices(items, weights=weights, k=rng.choice([1, 1, 1, 2, 2, 3]))
                    basket = {}
                    for item in picks:
                        basket[item] = basket.get(item, 0) + 1
                    planned.append((moment, rng.choices(methods, method_weights)[0], basket))
        sales = Sale.objects.bulk_create(
            Sale(
                cafe=cafe,
                sold_at=moment,
                recorded_by=user,
                payment_method=method,
                total=sum(item.price * qty for item, qty in basket.items()),
                cost_total=sum((item.cost or 0) * qty for item, qty in basket.items()),
            )
            for moment, method, basket in planned
        )
        SaleLine.objects.bulk_create(
            SaleLine(
                sale=sale, menu_item=item, name=item.name, quantity=qty, unit_price=item.price, unit_cost=item.cost
            )
            for sale, (_, _, basket) in zip(sales, planned, strict=True)
            for item, qty in basket.items()
        )
        self.stdout.write(f"Added {len(sales)} demo sales.")

    def _add_demo_barista(self, cafe):
        """A demo worker with two weeks of shifts, one of them clocked in away from the café."""
        User = get_user_model()
        if User.objects.filter(username="demo-barista").exists() or cafe.latitude is None:
            return
        barista = User.objects.create_user("demo-barista", first_name="Amina")
        barista.set_unusable_password()  # shows on the timesheet only; nobody logs in as her
        barista.save()
        StaffMembership.objects.create(user=barista, cafe=cafe, role=StaffMembership.Role.STAFF)
        rng = random.Random(7)
        today = cafe.local_now().date()
        lat, lng = float(cafe.latitude), float(cafe.longitude)
        for days_ago in range(14, 0, -1):
            day = today - dt.timedelta(days=days_ago)
            if day.weekday() == OpeningHours.Weekday.SUNDAY:
                continue
            start = dt.datetime.combine(day, dt.time(6, 45 + rng.randrange(12)), tzinfo=cafe.tz)
            end = dt.datetime.combine(day, dt.time(15, rng.randrange(20)), tzinfo=cafe.tz)
            away = days_ago == 3  # 0.006° is about 650 m: the timesheet will flag it
            in_lat = round(lat + (0.006 if away else rng.uniform(-0.0002, 0.0002)), 6)
            in_lng = round(lng + rng.uniform(-0.0002, 0.0002), 6)
            out_lat = round(lat + rng.uniform(-0.0002, 0.0002), 6)
            out_lng = round(lng + rng.uniform(-0.0002, 0.0002), 6)
            Shift.objects.create(
                cafe=cafe,
                user=barista,
                clock_in_at=start,
                clock_in_lat=in_lat,
                clock_in_lng=in_lng,
                clock_in_accuracy_m=rng.randrange(8, 30),
                clock_in_distance_m=round(distance_m(in_lat, in_lng, lat, lng)),
                clock_out_at=end,
                clock_out_lat=out_lat,
                clock_out_lng=out_lng,
                clock_out_accuracy_m=rng.randrange(8, 30),
                clock_out_distance_m=round(distance_m(out_lat, out_lng, lat, lng)),
            )
        self.stdout.write("Added demo barista Amina with two weeks of shifts.")

    def _add_demo_messages(self, cafe):
        """A few sample customer messages so the dashboard's Messages page has something to show."""
        Enquiry.objects.bulk_create(
            [
                Enquiry(
                    cafe=cafe,
                    kind=Enquiry.Kind.COMPLAINT,
                    name="Sample customer",
                    email="customer@example.com",
                    order_code="K7QD",
                    message="My flat white was lukewarm when I collected it this morning.",
                ),
                Enquiry(
                    cafe=cafe,
                    kind=Enquiry.Kind.QUESTION,
                    name="Sample visitor",
                    phone="123456789",
                    message="Do you have oat milk, and can I bring my dog inside?",
                ),
                Enquiry(
                    cafe=cafe,
                    kind=Enquiry.Kind.FEEDBACK,
                    name="Sample regular",
                    email="regular@example.com",
                    message="The banana bread is the best in Lisbon. Thank you!",
                ),
            ]
        )
