import datetime as dt
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cafes.models import StaffMembership
from cafes.tests.factories import make_cafe, make_item, make_user, set_hours
from customers.models import Customer, Enquiry
from ordering.models import Order

GOOD_PASSWORD = "steamed-milk-and-honey"


def url(name, cafe, *args):
    return reverse(f"cafes:{name}", args=[cafe.slug, *args])


class MenuSearchTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe()
        make_item(self.cafe, "Iced latte", description="Cold milk and espresso", category_name="Cold drinks")
        make_item(self.cafe, "Latte", description="Warm and milky")
        make_item(self.cafe, "Banana bread", price="3", category_name="Bakery")

    def search(self, query, cafe=None):
        return self.client.get(url("menu", cafe or self.cafe), {"q": query})

    def test_finds_items_by_name_case_insensitively(self):
        response = self.search("LATTE")
        self.assertContains(response, "2 results for")
        self.assertContains(response, "Iced latte")
        self.assertNotContains(response, "Banana bread")

    def test_every_word_must_match(self):
        response = self.search("iced latte")
        self.assertContains(response, "1 result for")
        self.assertNotContains(response, "Warm and milky")

    def test_matches_description_and_section(self):
        self.assertContains(self.search("espresso"), "Iced latte")
        self.assertContains(self.search("bakery"), "Banana bread")

    def test_no_results_says_so(self):
        response = self.search("pizza")
        self.assertContains(response, "Nothing on the menu matches")
        self.assertContains(response, "Show the full menu")

    def test_only_searches_this_cafes_menu(self):
        rival = make_cafe("rival")
        make_item(rival, "Rival latte")
        self.assertNotContains(self.search("latte"), "Rival latte")

    def test_menu_without_search_shows_everything(self):
        response = self.client.get(url("menu", self.cafe))
        self.assertContains(response, "Banana bread")
        self.assertContains(response, 'id="menu-search"')


class ContactTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cafe = make_cafe(phone="123456789")

    def send(self, **overrides):
        data = {"kind": "complaint", "name": " Ana  Silva ", "email": "ana@example.com", "phone": ""}
        data |= {"order_code": "ab2c", "message": "My latte was cold.", "website": ""}
        return self.client.post(url("contact", self.cafe), data | overrides)

    def test_page_shows_form_and_contact_details(self):
        response = self.client.get(url("contact", self.cafe))
        self.assertContains(response, "Send us a message")
        self.assertContains(response, "Complaint")
        self.assertContains(response, "tel:123456789")

    def test_message_is_saved_for_the_cafe(self):
        response = self.send()
        self.assertRedirects(response, url("contact_sent", self.cafe))
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.cafe, self.cafe)
        self.assertEqual(enquiry.kind, Enquiry.Kind.COMPLAINT)
        self.assertEqual(enquiry.name, "Ana Silva")
        self.assertEqual(enquiry.order_code, "AB2C")
        self.assertEqual(enquiry.status, Enquiry.Status.NEW)

    def test_needs_a_way_to_reply(self):
        response = self.send(email="", phone="")
        self.assertContains(response, "leave an email or phone number")
        self.assertFalse(Enquiry.objects.exists())

    def test_bots_filling_the_hidden_box_are_ignored(self):
        response = self.send(website="http://spam.example")
        self.assertRedirects(response, url("contact_sent", self.cafe))
        self.assertFalse(Enquiry.objects.exists())

    def test_limits_messages_from_one_address(self):
        for _ in range(5):
            self.send()
        response = self.send()
        self.assertContains(response, "sent several messages already")
        self.assertEqual(Enquiry.objects.count(), 5)

    def test_signed_in_customer_is_linked_and_prefilled(self):
        customer = Customer(cafe=self.cafe, name="Rui Costa", email="rui@example.com", phone="912 345 678")
        customer.set_password(GOOD_PASSWORD)
        customer.save()
        self.client.post(url("sign_in", self.cafe), {"email": "rui@example.com", "password": GOOD_PASSWORD})
        self.assertContains(self.client.get(url("contact", self.cafe)), 'value="rui@example.com"')
        self.send()
        self.assertEqual(Enquiry.objects.get().customer, customer)


class AccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cafe = make_cafe()

    def sign_up(self, cafe=None, **overrides):
        data = {"name": "Ana Silva", "email": "Ana@Example.com", "phone": "", "password": GOOD_PASSWORD}
        return self.client.post(url("sign_up", cafe or self.cafe), data | overrides)

    def sign_in(self, email="ana@example.com", password=GOOD_PASSWORD, cafe=None):
        return self.client.post(url("sign_in", cafe or self.cafe), {"email": email, "password": password})

    def test_sign_up_creates_account_and_signs_in(self):
        response = self.sign_up(wants_news="on")
        self.assertRedirects(response, self.cafe.get_absolute_url())
        customer = Customer.objects.get()
        self.assertEqual(customer.email, "ana@example.com")
        self.assertTrue(customer.wants_news)
        self.assertNotEqual(customer.password, GOOD_PASSWORD)
        self.assertTrue(customer.check_password(GOOD_PASSWORD))
        self.assertContains(self.client.get(url("account", self.cafe)), "Hi, Ana Silva")

    def test_weak_password_is_refused(self):
        response = self.sign_up(password="short")
        self.assertContains(response, "too short")
        self.assertFalse(Customer.objects.exists())

    def test_one_account_per_email_per_cafe(self):
        self.sign_up()
        self.client.post(url("sign_out", self.cafe))
        response = self.sign_up(email="ANA@example.com")
        self.assertContains(response, "already an account with this email")
        # The same person can still join a different café.
        self.sign_up(cafe=make_cafe("rival"))
        self.assertEqual(Customer.objects.count(), 2)

    def test_sign_in_and_out(self):
        self.sign_up()
        self.client.post(url("sign_out", self.cafe))
        self.assertRedirects(
            self.client.get(url("account", self.cafe)), f"{url('sign_in', self.cafe)}?next=/bean-house/account/"
        )
        self.assertRedirects(self.sign_in(email="ANA@EXAMPLE.COM"), self.cafe.get_absolute_url())
        self.assertEqual(self.client.get(url("account", self.cafe)).status_code, 200)

    def test_wrong_password_is_refused_then_locked_out(self):
        self.sign_up()
        self.client.post(url("sign_out", self.cafe))
        response = self.sign_in(password="wrong-password-here")
        self.assertContains(response, "match an account here")
        for _ in range(4):
            self.sign_in(password="wrong-password-here")
        self.assertContains(self.sign_in(), "Too many attempts")

    def test_sign_in_only_follows_local_next_links(self):
        self.sign_up()
        self.client.post(url("sign_out", self.cafe))
        response = self.client.post(
            url("sign_in", self.cafe),
            {"email": "ana@example.com", "password": GOOD_PASSWORD, "next": "https://evil.example/"},
        )
        self.assertRedirects(response, self.cafe.get_absolute_url())

    def test_account_belongs_to_one_cafe(self):
        rival = make_cafe("rival")
        self.sign_up()
        response = self.client.get(url("account", rival))
        self.assertRedirects(response, f"{url('sign_in', rival)}?next=/rival/account/")
        self.client.post(url("sign_out", self.cafe))
        self.assertContains(self.sign_in(cafe=rival), "match an account here")

    def test_customer_login_cannot_open_the_dashboard(self):
        self.sign_up()
        response = self.client.get(reverse("dashboard:overview", args=[self.cafe.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dashboard:login"), response.url)

    def test_update_details(self):
        self.sign_up()
        self.client.post(url("account", self.cafe), {"name": "Ana S", "phone": "912 345 678", "wants_news": "on"})
        customer = Customer.objects.get()
        self.assertEqual((customer.name, customer.phone, customer.wants_news), ("Ana S", "912 345 678", True))

    def test_header_shows_account_link_when_signed_in(self):
        self.assertContains(self.client.get(self.cafe.get_absolute_url()), "Sign in or sign up")
        self.sign_up()
        self.assertContains(self.client.get(self.cafe.get_absolute_url()), "Your account")


class SignedInOrderingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.cafe = make_cafe()
        set_hours(self.cafe, opens=dt.time(0), closes=dt.time(23, 59))
        self.latte = make_item(self.cafe, "Latte", price="3.50")
        moment = timezone.now().astimezone(self.cafe.tz).replace(hour=10, minute=0)
        patcher = mock.patch("django.utils.timezone.now", return_value=moment)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client.post(
            url("sign_up", self.cafe),
            {"name": "Ana Silva", "email": "ana@example.com", "phone": "912 345 678", "password": GOOD_PASSWORD},
        )

    def test_checkout_is_prefilled_and_order_shows_in_account(self):
        self.client.post(url("item", self.cafe, self.latte.pk), {"quantity": 2})
        basket = self.client.get(url("basket", self.cafe))
        self.assertContains(basket, 'value="Ana Silva"')
        self.assertContains(basket, 'value="912 345 678"')
        self.client.post(url("basket", self.cafe), {"name": "Ana Silva", "phone": "912 345 678", "pickup": "asap"})
        order = Order.objects.get()
        self.assertEqual(order.customer, Customer.objects.get())
        self.assertContains(self.client.get(url("account", self.cafe)), order.code)


class DashboardInboxTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe()
        self.owner = make_user("owner", self.cafe)
        self.barista = make_user("barista", self.cafe, role=StaffMembership.Role.STAFF)
        self.complaint = Enquiry.objects.create(
            cafe=self.cafe, kind=Enquiry.Kind.COMPLAINT, name="Ana", email="ana@example.com", message="Cold latte"
        )
        rival = make_cafe("rival")
        Enquiry.objects.create(cafe=rival, name="Someone else", phone="1234567", message="Rival question")

    def log_in(self, user):
        self.client.force_login(user)

    def test_staff_see_their_cafes_messages_only(self):
        self.log_in(self.barista)
        response = self.client.get(reverse("dashboard:inbox", args=[self.cafe.slug]))
        self.assertContains(response, "Cold latte")
        self.assertNotContains(response, "Rival question")

    def test_overview_flags_open_complaints(self):
        self.log_in(self.owner)
        response = self.client.get(reverse("dashboard:overview", args=[self.cafe.slug]))
        self.assertContains(response, "1 customer message")
        self.assertContains(response, "1 complaint")

    def test_mark_dealt_with_and_reopen(self):
        self.log_in(self.barista)
        resolve = reverse("dashboard:enquiry_resolve", args=[self.cafe.slug, self.complaint.pk])
        self.client.post(resolve, {"staff_note": "Called back, free coffee"})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Enquiry.Status.RESOLVED)
        self.assertEqual(self.complaint.resolved_by, self.barista)
        self.assertEqual(self.complaint.staff_note, "Called back, free coffee")
        done = self.client.get(reverse("dashboard:inbox", args=[self.cafe.slug]) + "?show=done")
        self.assertContains(done, "free coffee")
        self.client.post(resolve, {"action": "reopen"})
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, Enquiry.Status.NEW)

    def test_cannot_touch_another_cafes_message(self):
        other = Enquiry.objects.get(cafe__slug="rival")
        self.log_in(self.owner)
        response = self.client.post(reverse("dashboard:enquiry_resolve", args=[self.cafe.slug, other.pk]))
        self.assertEqual(response.status_code, 404)
        other.refresh_from_db()
        self.assertEqual(other.status, Enquiry.Status.NEW)

    def test_customer_list_is_for_owners(self):
        customer = Customer(cafe=self.cafe, name="Ana Silva", email="ana@example.com", wants_news=True)
        customer.set_password(GOOD_PASSWORD)
        customer.save()
        page = reverse("dashboard:customers", args=[self.cafe.slug])
        self.log_in(self.barista)
        self.assertEqual(self.client.get(page).status_code, 403)
        self.log_in(self.owner)
        response = self.client.get(page)
        self.assertContains(response, "ana@example.com")
        self.assertNotContains(response, customer.password)
