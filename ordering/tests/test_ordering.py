import datetime as dt
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cafes.models import StaffMembership
from cafes.tests.factories import make_cafe, make_item, make_user, set_hours
from operations import reports
from operations.models import Sale
from ordering import services
from ordering.models import Order

NAIROBI = dt.timezone(dt.timedelta(hours=3))


def at(hour, minute=0):
    """A moment today in Nairobi time (the test café's timezone)."""
    return timezone.now().astimezone(NAIROBI).replace(hour=hour, minute=minute, second=0, microsecond=0)


class OrderingTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.cafe = make_cafe()
        set_hours(self.cafe, opens=dt.time(7), closes=dt.time(19))
        self.latte = make_item(self.cafe, "Latte", price="3.50", cost=Decimal("1.00"), asks_sugar=True)
        self.bun = make_item(self.cafe, "Bun", price="2.00", category_name="Bakery")
        # Freeze "now" at 10:00 café time so the café is open.
        patcher = mock.patch("django.utils.timezone.now", return_value=at(10))
        patcher.start()
        self.addCleanup(patcher.stop)

    def add(self, item, quantity=1, sugar="normal", note=""):
        return self.client.post(
            reverse("cafes:item", args=[self.cafe.slug, item.pk]), {"quantity": quantity, "sugar": sugar, "note": note}
        )

    def checkout(self, pickup="asap", name="Wanjiru", phone="0712 345 678"):
        return self.client.post(
            reverse("cafes:basket", args=[self.cafe.slug]), {"name": name, "phone": phone, "pickup": pickup}
        )


class ItemPageTests(OrderingTestCase):
    def test_menu_cards_link_to_details(self):
        response = self.client.get(reverse("cafes:menu", args=[self.cafe.slug]))
        self.assertContains(response, reverse("cafes:item", args=[self.cafe.slug, self.latte.pk]))

    def test_details_page_shows_sugar_choice_only_when_offered(self):
        response = self.client.get(reverse("cafes:item", args=[self.cafe.slug, self.latte.pk]))
        self.assertContains(response, "No sugar")
        self.assertContains(response, "Special request")
        self.assertNotContains(self.client.get(reverse("cafes:item", args=[self.cafe.slug, self.bun.pk])), "No sugar")

    def test_other_cafes_item_is_not_found(self):
        rival_item = make_item(make_cafe("rival"), "Mocha")
        self.assertEqual(self.client.get(reverse("cafes:item", args=[self.cafe.slug, rival_item.pk])).status_code, 404)

    def test_sold_out_item_cannot_be_added(self):
        self.bun.is_available = False
        self.bun.save()
        self.assertContains(self.add(self.bun), "Sold out today")
        self.assertEqual(self.client.session.get(f"basket:{self.cafe.pk}", []), [])

    def test_no_ordering_when_switched_off(self):
        self.cafe.accepts_orders = False
        self.cafe.save()
        response = self.client.get(reverse("cafes:item", args=[self.cafe.slug, self.latte.pk]))
        self.assertContains(response, "Order at the counter")
        self.assertNotContains(response, "Add to order")


class BasketTests(OrderingTestCase):
    def test_same_drink_made_the_same_way_stacks_up(self):
        self.add(self.latte, 1, "none", "oat milk")
        self.add(self.latte, 2, "none", "oat  milk ")
        self.add(self.latte, 1, "extra")
        basket = self.client.session[f"basket:{self.cafe.pk}"]
        self.assertEqual(
            [(line["qty"], line["sugar"], line["note"]) for line in basket], [(3, "none", "oat milk"), (1, "extra", "")]
        )

    def test_bad_sugar_or_quantity_is_refused(self):
        self.assertContains(self.add(self.latte, sugar="loads"), "Select a valid choice")
        self.assertContains(self.add(self.latte, quantity=500), "less than or equal to 20")
        self.assertEqual(self.client.session.get(f"basket:{self.cafe.pk}", []), [])

    def test_update_and_remove(self):
        self.add(self.latte)
        self.add(self.bun)
        url = reverse("cafes:basket_update", args=[self.cafe.slug])
        self.client.post(url, {"index": 0, "quantity": 4})
        self.client.post(url, {"index": 1, "quantity": 0})
        self.assertEqual(
            self.client.session[f"basket:{self.cafe.pk}"],
            [{"item": self.latte.pk, "qty": 4, "sugar": "normal", "note": ""}],
        )
        self.assertContains(self.client.get(reverse("cafes:basket", args=[self.cafe.slug])), "$14")


class CheckoutTests(OrderingTestCase):
    def test_place_order(self):
        self.add(self.latte, 2, "none", "Oat milk please")
        self.add(self.bun)
        response = self.checkout()
        order = Order.objects.get()
        self.assertRedirects(response, reverse("cafes:order_status", args=[self.cafe.slug, order.token]))
        self.assertEqual(order.total, Decimal("9.00"))
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertIsNone(order.pickup_at)
        line = order.lines.get(name="Latte")
        self.assertEqual(
            (line.quantity, line.sugar, line.note, line.unit_cost), (2, "none", "Oat milk please", Decimal("1.00"))
        )
        self.assertEqual(self.client.session.get(f"basket:{self.cafe.pk}"), None)
        page = self.client.get(response.url)
        self.assertContains(page, order.code)
        self.assertContains(page, "No sugar")
        # The customer's other pages link back to the order while it's on its way.
        self.assertContains(self.client.get(reverse("cafes:menu", args=[self.cafe.slug])), f"Your order {order.code}")

    def test_prices_come_from_the_menu_at_checkout(self):
        self.add(self.bun)
        self.bun.price = Decimal("2.50")
        self.bun.save()
        self.checkout()
        self.assertEqual(Order.objects.get().total, Decimal("2.50"))

    def test_item_selling_out_before_checkout_blocks_the_order(self):
        self.add(self.bun)
        self.bun.is_available = False
        self.bun.save()
        self.assertContains(self.checkout(), "just sold out")
        self.assertFalse(Order.objects.exists())

    def test_details_are_required(self):
        self.add(self.bun)
        response = self.checkout(name="", phone="call me")
        self.assertContains(response, "This field is required")
        self.assertContains(response, "phone number we can call")
        self.assertFalse(Order.objects.exists())

    def test_empty_basket(self):
        self.assertContains(self.checkout(), "Your basket is empty")

    def test_pickup_later_today(self):
        self.add(self.bun)
        _, slots = services.pickup_options(self.cafe)
        self.assertEqual(slots[0], at(10, 15))
        self.assertEqual(slots[-1], at(18, 45))
        self.checkout(pickup=slots[2].isoformat())
        self.assertEqual(Order.objects.get().pickup_at, at(10, 45))

    def test_made_up_pickup_time_is_refused(self):
        self.add(self.bun)
        self.assertContains(self.checkout(pickup=at(23).isoformat()), "pickup time isn&#x27;t available")

    def test_closed_cafe_only_takes_orders_for_later_today(self):
        with mock.patch("django.utils.timezone.now", return_value=at(6, 10)):
            asap, slots = services.pickup_options(self.cafe)
            self.assertFalse(asap)
            self.assertEqual(slots[0], at(7))
            self.add(self.bun)
            self.assertContains(self.checkout(pickup="asap"), "pickup time isn&#x27;t available")
        with mock.patch("django.utils.timezone.now", return_value=at(20)):
            self.assertFalse(services.can_order(self.cafe))
            self.assertContains(
                self.client.get(reverse("cafes:basket", args=[self.cafe.slug])), "not taking online orders"
            )

    def test_order_flood_is_limited(self):
        for _ in range(services.ORDERS_PER_WINDOW):
            self.add(self.bun)
            self.checkout()
        self.add(self.bun)
        self.assertContains(self.checkout(), "placed several orders")
        self.assertEqual(Order.objects.count(), services.ORDERS_PER_WINDOW)

    def test_tracking_link_needs_the_secret_token(self):
        self.add(self.bun)
        self.checkout()
        order = Order.objects.get()
        rival = make_cafe("rival")
        self.assertEqual(self.client.get(f"/{rival.slug}/order/{order.token}/").status_code, 404)
        self.assertEqual(self.client.get(f"/{self.cafe.slug}/order/{order.code}/").status_code, 404)


class StaffBoardTests(OrderingTestCase):
    def setUp(self):
        super().setUp()
        self.add(self.latte, 2, "less", "extra hot")
        self.checkout()
        self.order = Order.objects.get()
        self.client.logout()
        self.staff = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        self.client.force_login(self.staff)

    def move(self, status, **extra):
        return self.client.post(
            reverse("dashboard:order_status", args=[self.cafe.slug, self.order.pk]), {"status": status, **extra}
        )

    def test_board_shows_order_with_sugar_and_request(self):
        response = self.client.get(reverse("dashboard:orders", args=[self.cafe.slug]))
        self.assertContains(response, self.order.code)
        self.assertContains(response, "Less sugar")
        self.assertContains(response, "extra hot")
        self.assertContains(self.client.get(reverse("dashboard:overview", args=[self.cafe.slug])), "1 online order")

    def test_full_journey_records_a_sale(self):
        self.move("preparing")
        self.move("ready")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.READY)
        self.assertFalse(Sale.objects.exists())
        self.move("collected", payment_method="mobile")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.COLLECTED)
        sale = self.order.sale
        self.assertEqual((sale.total, sale.payment_method, sale.recorded_by), (Decimal("7.00"), "mobile", self.staff))
        report = reports.sales_report(self.cafe, "today")
        self.assertEqual(report["revenue"], Decimal("7.00"))
        self.assertEqual(report["best_sellers"][0]["name"], "Latte")

    def test_cannot_skip_to_collected_or_go_backwards(self):
        self.move("collected")
        self.move("preparing")
        self.move("new")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PREPARING)
        self.assertFalse(Sale.objects.exists())

    def test_double_tap_collects_once(self):
        self.move("preparing")
        self.move("ready")
        self.move("collected")
        self.move("collected")
        self.assertEqual(Sale.objects.count(), 1)

    def test_cancel(self):
        self.move("cancelled")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.move("preparing")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_other_cafes_orders_are_hidden(self):
        rival = make_cafe("rival")
        make_user("rival-owner", rival)
        self.assertEqual(self.client.get(reverse("dashboard:orders", args=["rival"])).status_code, 404)
        rival_owner = rival.memberships.get().user
        self.client.force_login(rival_owner)
        self.assertNotContains(self.client.get(reverse("dashboard:orders", args=["rival"])), self.order.code)
        self.assertEqual(self.move("cancelled").status_code, 404)
