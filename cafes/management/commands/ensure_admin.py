"""Create the platform admin login from environment variables, once.

Lets a host like Render set up the first admin without shell access.
Does nothing if the variables are missing or the user already exists.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a superuser from DJANGO_SUPERUSER_USERNAME / DJANGO_SUPERUSER_PASSWORD if it doesn't exist."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not username or not password:
            self.stdout.write("DJANGO_SUPERUSER_USERNAME/PASSWORD not set; skipping admin creation.")
            return
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"Admin '{username}' already exists.")
            return
        User.objects.create_superuser(username, email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""), password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin '{username}'."))
