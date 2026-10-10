import datetime as dt

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from cafes.models import Closure, MenuItem, OpeningHours, StaffMembership
from cafes.tests.factories import PASSWORD, make_cafe, make_item, make_user


class AccessTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe("bean-house")
        self.other = make_cafe("rival-cafe")
        self.owner = make_user("owner", self.cafe)
        self.other_item = make_item(self.other, "Rival Mocha")

    def test_login_required(self):
        response = self.client.get(reverse("dashboard:menu", args=["bean-house"]))
        self.assertRedirects(response, "/dashboard/login/?next=/dashboard/bean-house/menu/")

    def test_cannot_open_another_cafes_dashboard(self):
        self.client.force_login(self.owner)
        for name in ["overview", "menu", "hours", "settings"]:
            with self.subTest(name):
                self.assertEqual(self.client.get(reverse(f"dashboard:{name}", args=["rival-cafe"])).status_code, 404)

    def test_cannot_touch_another_cafes_item_through_own_cafe_url(self):
        self.client.force_login(self.owner)
        pk = self.other_item.pk
        self.assertEqual(self.client.get(reverse("dashboard:item_edit", args=["bean-house", pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dashboard:item_toggle", args=["bean-house", pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("dashboard:item_delete", args=["bean-house", pk])).status_code, 404)
        self.other_item.refresh_from_db()
        self.assertTrue(self.other_item.is_available)

    def test_cannot_put_item_in_another_cafes_section(self):
        self.client.force_login(self.owner)
        make_item(self.cafe, "Own item")
        response = self.client.post(
            reverse("dashboard:item_add", args=["bean-house"]),
            {
                "category": self.other_item.category.pk,
                "name": "Sneaky",
                "price": "10",
                "position": 0,
                "is_available": "on",
            },
        )
        self.assertEqual(response.status_code, 200)  # form re-shown with an error
        self.assertFalse(MenuItem.objects.filter(name="Sneaky").exists())

    def test_staff_cannot_edit_cafe_details(self):
        staff = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse("dashboard:settings", args=["bean-house"])).status_code, 403)
        self.assertEqual(self.client.get(reverse("dashboard:menu", args=["bean-house"])).status_code, 200)

    def test_single_cafe_user_goes_straight_to_it(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get(reverse("dashboard:home")), "/dashboard/bean-house/")


class MenuManagementTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe()
        self.client.force_login(make_user("owner", self.cafe))

    def test_add_section_and_item(self):
        self.client.post(reverse("dashboard:category_add", args=["bean-house"]), {"name": "Hot drinks", "position": 0})
        category = self.cafe.menu_categories.get()
        response = self.client.post(
            reverse("dashboard:item_add", args=["bean-house"]),
            {"category": category.pk, "name": "Flat white", "price": "270", "position": 0, "is_available": "on"},
        )
        self.assertRedirects(response, "/dashboard/bean-house/menu/")
        self.assertEqual(MenuItem.objects.get().name, "Flat white")

    def test_duplicate_section_name_rejected(self):
        make_item(self.cafe, category_name="Hot drinks")
        response = self.client.post(
            reverse("dashboard:category_add", args=["bean-house"]), {"name": "hot drinks", "position": 1}
        )
        self.assertContains(response, "already have a section")

    def test_negative_price_rejected(self):
        item = make_item(self.cafe)
        response = self.client.post(
            reverse("dashboard:item_edit", args=["bean-house", item.pk]),
            {"category": item.category.pk, "name": item.name, "price": "-5", "position": 0},
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.price, 250)

    def test_toggle_sold_out_with_htmx_returns_row(self):
        item = make_item(self.cafe)
        response = self.client.post(
            reverse("dashboard:item_toggle", args=["bean-house", item.pk]), headers={"HX-Request": "true"}
        )
        self.assertContains(response, "Sold out")
        self.assertNotContains(response, "<html")
        item.refresh_from_db()
        self.assertFalse(item.is_available)

    def test_cannot_delete_section_with_items(self):
        item = make_item(self.cafe)
        self.client.post(reverse("dashboard:category_delete", args=["bean-house", item.category.pk]))
        self.assertTrue(MenuItem.objects.filter(pk=item.pk).exists())

    def test_toggle_requires_post(self):
        item = make_item(self.cafe)
        self.assertEqual(
            self.client.get(reverse("dashboard:item_toggle", args=["bean-house", item.pk])).status_code, 405
        )


class HoursTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe()
        self.client.force_login(make_user("owner", self.cafe))
        self.url = reverse("dashboard:hours", args=["bean-house"])

    def _post(self, overrides):
        self.client.get(self.url)  # creates the seven rows
        rows = list(OpeningHours.objects.filter(cafe=self.cafe).order_by("weekday"))
        data = {"hours-TOTAL_FORMS": 7, "hours-INITIAL_FORMS": 7}
        for i, row in enumerate(rows):
            data[f"hours-{i}-id"] = row.pk
            data[f"hours-{i}-opens"] = "08:00"
            data[f"hours-{i}-closes"] = "17:00"
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_page_creates_a_row_per_day(self):
        self.client.get(self.url)
        self.assertEqual(OpeningHours.objects.filter(cafe=self.cafe).count(), 7)

    def test_save_hours(self):
        response = self._post({"hours-6-is_closed": "on", "hours-6-opens": "", "hours-6-closes": ""})
        self.assertRedirects(response, self.url)
        monday = OpeningHours.objects.get(cafe=self.cafe, weekday=0)
        self.assertEqual(monday.opens, dt.time(8))
        self.assertTrue(OpeningHours.objects.get(cafe=self.cafe, weekday=6).is_closed)

    def test_open_day_without_times_rejected(self):
        response = self._post({"hours-0-opens": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set both opening and closing times")

    def test_cannot_submit_another_cafes_hours_rows(self):
        other = make_cafe("rival-cafe")
        self.client.get(self.url)
        OpeningHours.objects.create(cafe=other, weekday=0, opens=dt.time(6), closes=dt.time(7))
        rival_row = OpeningHours.objects.get(cafe=other)
        self._post({"hours-0-id": rival_row.pk, "hours-0-opens": "01:00"})
        rival_row.refresh_from_db()
        self.assertEqual(rival_row.opens, dt.time(6))

    def test_add_and_remove_closure(self):
        self.client.post(
            reverse("dashboard:closure_add", args=["bean-house"]),
            {"closure-date": "2026-12-25", "closure-note": "Christmas"},
        )
        closure = Closure.objects.get(cafe=self.cafe)
        self.client.post(reverse("dashboard:closure_delete", args=["bean-house", closure.pk]))
        self.assertFalse(Closure.objects.exists())


@override_settings(LOGIN_MAX_ATTEMPTS=3)
class LoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cafe = make_cafe()
        make_user("owner", self.cafe)
        self.url = reverse("dashboard:login")

    def test_login_works(self):
        response = self.client.post(self.url, {"username": "owner", "password": PASSWORD})
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_locked_out_after_repeated_failures(self):
        for _ in range(3):
            self.client.post(self.url, {"username": "owner", "password": "wrong"})
        response = self.client.post(self.url, {"username": "owner", "password": PASSWORD})
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Too many failed attempts", status_code=429)

    def test_passwords_hashed_with_argon2(self):
        from django.contrib.auth import get_user_model

        self.assertTrue(get_user_model().objects.get(username="owner").password.startswith("argon2"))


class PicturePickerTests(TestCase):
    def test_owner_can_choose_built_in_picture(self):
        cafe = make_cafe()
        self.client.force_login(make_user("owner", cafe))
        item = make_item(cafe)
        response = self.client.post(
            reverse("dashboard:item_edit", args=["bean-house", item.pk]),
            {"category": item.category.pk, "name": item.name, "price": "3", "position": 0, "stock_image": "cappuccino"},
        )
        self.assertRedirects(response, "/dashboard/bean-house/menu/")
        item.refresh_from_db()
        self.assertEqual(item.stock_image, "cappuccino")
