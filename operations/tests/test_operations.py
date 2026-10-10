import datetime as dt
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cafes.models import Cafe, StaffMembership
from cafes.tests.factories import PASSWORD, make_cafe, make_item, make_user
from operations import reports, services
from operations.models import Sale, Shift, distance_m

CAFE_LAT, CAFE_LNG = Decimal("-0.420130"), Decimal("36.947600")


def url(name, *args, cafe="bean-house"):
    return reverse(f"dashboard:{name}", args=[cafe, *args])


class RecordSaleTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe()
        self.owner = make_user("owner", self.cafe)
        self.latte = make_item(self.cafe, "Latte", price="3.50", cost=Decimal("1.00"))
        self.bun = make_item(self.cafe, "Bun", price="2.00", category_name="Bakery")

    def test_prices_and_costs_come_from_the_menu(self):
        sale = services.record_sale(self.cafe, self.owner, {self.latte.pk: 2, self.bun.pk: 1}, "cash")
        self.assertEqual(sale.total, Decimal("9.00"))
        self.assertEqual(sale.cost_total, Decimal("2.00"))  # the bun has no cost, so it adds nothing
        self.assertEqual(sale.lines.count(), 2)

    def test_past_sales_keep_their_price_after_a_menu_change(self):
        sale = services.record_sale(self.cafe, self.owner, {self.latte.pk: 1}, "cash")
        self.latte.price = Decimal("9.99")
        self.latte.save()
        sale.recalculate()
        self.assertEqual(sale.total, Decimal("3.50"))

    def test_rejects_bad_input(self):
        rival_item = make_item(make_cafe("rival"), "Rival mocha")
        for quantities, method in [
            ({}, "cash"),
            ({self.latte.pk: 0}, "cash"),
            ({self.latte.pk: 1}, "bitcoin"),
            ({self.latte.pk: 100}, "cash"),
            ({rival_item.pk: 1}, "cash"),
        ]:
            with self.subTest(quantities=quantities, method=method), self.assertRaises(ValidationError):
                services.record_sale(self.cafe, self.owner, quantities, method)
        self.assertFalse(Sale.objects.exists())

    def test_till_page_records_a_sale(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            url("till"), {f"qty_{self.latte.pk}": "2", f"qty_{self.bun.pk}": "", "payment_method": "mobile"}
        )
        self.assertRedirects(response, url("till"))
        sale = Sale.objects.get()
        self.assertEqual((sale.total, sale.payment_method, sale.recorded_by), (Decimal("7.00"), "mobile", self.owner))

    def test_till_ignores_a_price_sent_by_the_browser(self):
        self.client.force_login(self.owner)
        self.client.post(url("till"), {f"qty_{self.latte.pk}": "1", "price": "0.01", "payment_method": "cash"})
        self.assertEqual(Sale.objects.get().total, Decimal("3.50"))

    def test_staff_can_use_the_till_but_not_cancel_sales(self):
        staff = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url("till")).status_code, 200)
        sale = services.record_sale(self.cafe, staff, {self.latte.pk: 1}, "cash")
        self.assertEqual(self.client.post(url("sale_void", sale.pk)).status_code, 403)
        sale.refresh_from_db()
        self.assertFalse(sale.is_void)

    def test_owner_cancels_a_sale_and_it_leaves_the_reports(self):
        sale = services.record_sale(self.cafe, self.owner, {self.latte.pk: 1}, "cash")
        self.client.force_login(self.owner)
        self.client.post(url("sale_void", sale.pk))
        sale.refresh_from_db()
        self.assertTrue(sale.is_void)
        self.assertEqual(reports.sales_report(self.cafe, "today")["count"], 0)

    def test_cannot_cancel_another_cafes_sale(self):
        rival = make_cafe("rival")
        rival_sale = services.record_sale(rival, None, {make_item(rival, "Mocha").pk: 1}, "cash")
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url("sale_void", rival_sale.pk)).status_code, 404)
        rival_sale.refresh_from_db()
        self.assertFalse(rival_sale.is_void)


class ReportTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe(timezone="Africa/Nairobi")  # UTC+3
        self.owner = make_user("owner", self.cafe)
        self.latte = make_item(self.cafe, "Latte", price="4.00", cost=Decimal("1.00"))
        self.bun = make_item(self.cafe, "Bun", price="2.00")

    def sell(self, quantities, when=None, method="cash"):
        sale = services.record_sale(self.cafe, self.owner, quantities, method)
        if when:
            Sale.objects.filter(pk=sale.pk).update(sold_at=when)
        return sale

    def test_profit_only_counts_items_with_a_cost(self):
        self.sell({self.latte.pk: 2, self.bun.pk: 3})
        report = reports.sales_report(self.cafe, "today")
        self.assertEqual(report["revenue"], Decimal("14.00"))
        self.assertEqual(report["profit"], Decimal("6.00"))
        self.assertEqual(report["margin"], Decimal("75"))
        self.assertEqual(report["uncosted_revenue"], Decimal("6.00"))

    def test_best_sellers_rank_by_quantity(self):
        self.sell({self.latte.pk: 1, self.bun.pk: 5})
        self.sell({self.latte.pk: 2})
        best = reports.sales_report(self.cafe, "today")["best_sellers"]
        self.assertEqual([(b["name"], b["quantity"]) for b in best], [("Bun", 5), ("Latte", 3)])
        self.assertIsNone(best[0]["profit"])
        self.assertEqual(best[1]["profit"], Decimal("9.00"))

    def test_days_follow_the_cafes_timezone(self):
        # 22:30 UTC yesterday is 01:30 today in Nairobi, so it counts as today.
        today = self.cafe.local_now().date()
        late = dt.datetime.combine(today - dt.timedelta(days=1), dt.time(22, 30), tzinfo=dt.UTC)
        self.sell({self.latte.pk: 1}, when=late)
        report = reports.sales_report(self.cafe, "7")
        self.assertEqual(len(report["days"]), 7)
        self.assertEqual(report["days"][-1], {"date": today, "revenue": Decimal("4.00")})
        self.assertEqual(report["busy_hours"], [{"hour": 1, "sales": 1}])

    def test_old_and_other_cafes_sales_are_left_out(self):
        self.sell({self.latte.pk: 1}, when=timezone.now() - dt.timedelta(days=40))
        rival = make_cafe("rival")
        services.record_sale(rival, None, {make_item(rival, "Mocha").pk: 1}, "cash")
        self.assertEqual(reports.sales_report(self.cafe, "30")["count"], 0)
        self.assertEqual(reports.sales_report(self.cafe, "90")["count"], 1)

    def test_reports_page(self):
        self.sell({self.latte.pk: 1})
        self.client.force_login(self.owner)
        for period in ["today", "7", "30", "90", "nonsense"]:
            with self.subTest(period):
                response = self.client.get(url("reports"), {"period": period})
                self.assertContains(response, "Latte")
        self.assertContains(self.client.get(url("reports")), "1 menu item has no cost yet")

    def test_owner_only_pages(self):
        staff = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        self.client.force_login(staff)
        for name in ["reports", "shifts", "team"]:
            with self.subTest(name):
                self.assertEqual(self.client.get(url(name)).status_code, 403)
        self.assertNotContains(self.client.get(url("overview")), "Sales today")

    def test_other_cafes_pages_are_hidden(self):
        make_cafe("rival")
        self.client.force_login(self.owner)
        for name in ["till", "reports", "clock", "shifts", "team"]:
            with self.subTest(name):
                self.assertEqual(self.client.get(url(name, cafe="rival")).status_code, 404)


class ClockTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe(latitude=CAFE_LAT, longitude=CAFE_LNG, clock_in_radius_m=150)
        self.worker = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        self.client.force_login(self.worker)

    def clock(self, action, lat=CAFE_LAT, lng=CAFE_LNG, **extra):
        return self.client.post(url("clock_action"), {"action": action, "lat": lat, "lng": lng, **extra}, follow=True)

    def test_distance(self):
        self.assertAlmostEqual(distance_m(0, 0, 0, 1), 111_195, delta=10)  # one degree at the equator

    def test_clock_in_and_out_at_the_cafe(self):
        response = self.clock("in", accuracy="12")
        self.assertContains(response, "Clocked in at")
        shift = Shift.objects.get()
        self.assertTrue(shift.is_open)
        self.assertEqual((shift.clock_in_distance_m, shift.clock_in_accuracy_m), (0, 12))
        self.assertFalse(shift.flagged)
        self.assertContains(self.clock("out"), "Clocked out")
        shift.refresh_from_db()
        self.assertFalse(shift.is_open)

    def test_clocking_in_away_from_the_cafe_is_flagged(self):
        response = self.clock("in", lat=CAFE_LAT + Decimal("0.01"))  # about 1.1 km north
        self.assertContains(response, "away from the café")
        shift = Shift.objects.get()
        self.assertGreater(shift.clock_in_distance_m, 1000)
        self.assertTrue(shift.flagged)

    def test_location_is_required(self):
        self.assertContains(self.clock("in", lat="", lng=""), "couldn&#x27;t get your location")
        self.assertContains(self.clock("in", lat="91", lng="0"), "doesn&#x27;t look right")
        self.assertFalse(Shift.objects.exists())

    def test_cannot_clock_in_twice_or_out_without_a_shift(self):
        self.assertContains(self.clock("out"), "not clocked in")
        self.clock("in")
        self.assertContains(self.clock("in"), "already clocked in")
        self.assertEqual(Shift.objects.count(), 1)

    def test_no_map_pin_still_records_location(self):
        self.cafe.latitude = self.cafe.longitude = None
        self.cafe.save()
        self.clock("in")
        shift = Shift.objects.get()
        self.assertIsNone(shift.clock_in_distance_m)
        self.assertFalse(shift.flagged)

    def test_clocking_needs_post(self):
        self.assertEqual(self.client.get(url("clock_action")).status_code, 405)

    def test_owner_sees_shifts_and_who_is_on(self):
        self.clock("in", lat=CAFE_LAT + Decimal("0.01"))
        owner = make_user("owner", self.cafe)
        self.client.force_login(owner)
        response = self.client.get(url("shifts"))
        self.assertContains(response, "barista")
        self.assertContains(response, "Away from café")
        self.assertContains(self.client.get(url("overview")), "barista (since")

    def test_timesheet_totals(self):
        start = timezone.now() - dt.timedelta(hours=10)
        Shift.objects.create(
            cafe=self.cafe,
            user=self.worker,
            clock_in_at=start,
            clock_out_at=start + dt.timedelta(hours=8),
            clock_in_lat=CAFE_LAT,
            clock_in_lng=CAFE_LNG,
        )
        workers = reports.timesheet(self.cafe, "7")["workers"]
        self.assertEqual(len(workers), 1)
        self.assertAlmostEqual(workers[0]["hours"], 8.0)


class TeamTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe()
        self.owner = make_user("owner", self.cafe)
        self.client.force_login(self.owner)

    def test_owner_adds_a_worker_who_can_log_in(self):
        data = {"first_name": "Mary", "username": "mary.k", "password": "long-enough-pass-42", "role": "staff"}
        response = self.client.post(url("team"), data)
        self.assertRedirects(response, url("team"))
        mary = get_user_model().objects.get(username="mary.k")
        self.assertEqual(mary.memberships.get().role, StaffMembership.Role.STAFF)
        self.client.logout()
        self.assertTrue(self.client.login(username="mary.k", password="long-enough-pass-42"))

    def test_rejects_taken_username_and_weak_password(self):
        response = self.client.post(
            url("team"), {"first_name": "Owner", "username": "OWNER", "password": "123", "role": "staff"}
        )
        self.assertContains(response, "That username is taken")
        self.assertContains(response, "This password is too short")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_removing_a_worker_switches_off_their_login(self):
        worker = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        self.client.post(url("team_remove", worker.memberships.get().pk))
        worker.refresh_from_db()
        self.assertFalse(worker.is_active)
        self.assertFalse(self.client.login(username="barista", password=PASSWORD))

    def test_worker_at_two_cafes_keeps_the_other(self):
        other = make_cafe("second")
        worker = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        StaffMembership.objects.create(user=worker, cafe=other)
        self.client.post(url("team_remove", worker.memberships.get(cafe=self.cafe).pk))
        worker.refresh_from_db()
        self.assertTrue(worker.is_active)

    def test_cannot_remove_yourself_or_another_cafes_staff(self):
        self.client.post(url("team_remove", self.owner.memberships.get().pk))
        self.assertTrue(self.owner.memberships.exists())
        rival_member = make_user("rival", make_cafe("rival"))
        response = self.client.post(url("team_remove", rival_member.memberships.get().pk))
        self.assertEqual(response.status_code, 404)


class DemoSeedTests(TestCase):
    def test_demo_has_sales_costs_and_shifts_and_reruns_safely(self):
        call_command("seed_demo", owner_password="demo-pass-for-tests-1", stdout=StringIO())
        cafe = Cafe.objects.get(slug="bean-house")
        sales = Sale.objects.filter(cafe=cafe).count()
        self.assertGreater(sales, 300)
        self.assertGreater(reports.sales_report(cafe, "30")["profit"], 0)
        self.assertTrue(Shift.objects.filter(cafe=cafe, user__username="demo-barista").exists())
        call_command("seed_demo", owner_password="demo-pass-for-tests-1", stdout=StringIO())
        self.assertEqual(Sale.objects.filter(cafe=cafe).count(), sales)
