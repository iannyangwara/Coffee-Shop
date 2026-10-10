"""Create a realistic demo café so there's something to show and click around."""

import datetime as dt
import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from cafes.models import Cafe, MenuCategory, MenuItem, OpeningHours, StaffMembership

MENU = {
    "Hot drinks": [
        ("Espresso", "Single shot of our house roast.", "150", True),
        ("Cappuccino", "Espresso, steamed milk and a thick layer of foam.", "250", True),
        ("Café latte", "Smooth and milky.", "250", False),
        ("Kenyan tea", "Strong black tea brewed with milk and spices.", "120", False),
        ("Hot chocolate", "Rich cocoa with steamed milk.", "280", False),
    ],
    "Cold drinks": [
        ("Iced latte", "Espresso over ice with cold milk.", "300", False),
        ("Fresh passion juice", "Squeezed every morning.", "200", False),
    ],
    "Bakery": [
        ("Butter croissant", "Baked in-house every morning.", "180", True),
        ("Banana bread", "Moist slice with walnuts.", "200", False),
        ("Mandazi (3 pcs)", "Lightly sweet East African doughnuts.", "100", False),
    ],
    "Breakfast": [
        ("Full breakfast", "Eggs, sausage, toast, beans and grilled tomato.", "650", False),
        ("Avocado toast", "Smashed avocado on sourdough with chilli flakes.", "450", True),
    ],
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
        cafe, created = Cafe.objects.get_or_create(
            slug="bean-house",
            defaults=dict(
                name="Bean House",
                tagline="Fresh coffee and home baking in the heart of town",
                about=(
                    "Bean House is a family-run café serving locally grown coffee, "
                    "fresh bakes and a proper breakfast.\n\nPull up a chair, the Wi-Fi is free."
                ),
                phone="+254 712 345 678",
                whatsapp="254712345678",
                email="hello@beanhouse.example",
                instagram="beanhouse",
                address="Kenyatta Avenue, opposite the market",
                town="Nyeri",
                latitude=Decimal("-0.420130"),
                longitude=Decimal("36.947600"),
            ),
        )
        if not created:
            self.stdout.write("Demo café already exists; leaving it as it is.")
        else:
            for day in OpeningHours.Weekday.values:
                if day == OpeningHours.Weekday.SUNDAY:
                    OpeningHours.objects.create(cafe=cafe, weekday=day, opens=dt.time(9), closes=dt.time(14))
                else:
                    OpeningHours.objects.create(cafe=cafe, weekday=day, opens=dt.time(7), closes=dt.time(19))
            for position, (category_name, items) in enumerate(MENU.items()):
                category = MenuCategory.objects.create(cafe=cafe, name=category_name, position=position)
                for item_position, (name, description, price, featured) in enumerate(items):
                    MenuItem.objects.create(
                        category=category,
                        name=name,
                        description=description,
                        price=Decimal(price),
                        is_featured=featured,
                        position=item_position,
                    )
            self.stdout.write(self.style.SUCCESS(f"Created demo café at {cafe.get_absolute_url()}"))

        User = get_user_model()
        user = User.objects.filter(username=owner_username).first()
        if user is None:
            if not owner_password:
                self.stderr.write("No owner login created: pass --owner-password or set DEMO_OWNER_PASSWORD.")
                return
            user = User.objects.create_user(owner_username, password=owner_password, first_name="Demo")
            self.stdout.write(self.style.SUCCESS(f"Created owner login '{owner_username}'."))
        StaffMembership.objects.get_or_create(user=user, cafe=cafe, defaults={"role": StaffMembership.Role.OWNER})
