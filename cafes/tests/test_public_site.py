from django.test import TestCase
from django.urls import reverse

from .factories import make_cafe, make_item, set_hours


class PublicSiteTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe(tagline="Best coffee in Nyeri", latitude="-0.42", longitude="36.94")
        set_hours(self.cafe)
        make_item(self.cafe, "Cappuccino", "250", is_featured=True)
        make_item(self.cafe, "Latte", "260", is_available=False)

    def test_home_shows_featured_items(self):
        response = self.client.get(reverse("cafes:home", args=["bean-house"]))
        self.assertContains(response, "Best coffee in Nyeri")
        self.assertContains(response, "Cappuccino")
        self.assertNotContains(response, "Latte")

    def test_menu_lists_items_and_marks_sold_out(self):
        response = self.client.get(reverse("cafes:menu", args=["bean-house"]))
        self.assertContains(response, "$250")
        self.assertContains(response, "Sold out today")

    def test_visit_page_shows_hours_and_map(self):
        response = self.client.get(reverse("cafes:visit", args=["bean-house"]))
        self.assertContains(response, "7:00 AM – 7:00 PM")
        self.assertContains(response, "openstreetmap.org")

    def test_unpublished_cafe_is_hidden(self):
        self.cafe.is_published = False
        self.cafe.save()
        self.assertEqual(self.client.get(reverse("cafes:home", args=["bean-house"])).status_code, 404)

    def test_unknown_cafe_is_404(self):
        self.assertEqual(self.client.get("/no-such-cafe/").status_code, 404)

    def test_other_cafes_items_never_leak(self):
        other = make_cafe("other-cafe")
        make_item(other, "Secret Brew", "999")
        response = self.client.get(reverse("cafes:menu", args=["bean-house"]))
        self.assertNotContains(response, "Secret Brew")

    def test_platform_home_lists_published_cafes(self):
        make_cafe("hidden-cafe", name="Hidden Cafe", is_published=False)
        response = self.client.get("/")
        self.assertContains(response, "Bean House")
        self.assertNotContains(response, "Hidden Cafe")

    def test_healthcheck(self):
        self.assertEqual(self.client.get("/healthz").content, b"ok")
