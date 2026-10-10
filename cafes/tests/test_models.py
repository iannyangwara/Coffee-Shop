import datetime as dt
import zoneinfo
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from cafes.models import Cafe, Closure, OpeningHours
from cafes.templatetags.cafe_tags import money

from .factories import make_cafe, set_hours

NAIROBI = zoneinfo.ZoneInfo("Africa/Nairobi")


def at(year, month, day, hour, minute=0):
    return dt.datetime(year, month, day, hour, minute, tzinfo=NAIROBI)


class OpenNowTests(TestCase):
    def setUp(self):
        self.cafe = make_cafe()
        set_hours(self.cafe, dt.time(7), dt.time(19))

    def test_open_during_hours(self):
        self.assertTrue(self.cafe.is_open_at(at(2026, 10, 7, 12)))  # Wednesday noon

    def test_closed_before_opening_and_at_closing_time(self):
        self.assertFalse(self.cafe.is_open_at(at(2026, 10, 7, 6, 59)))
        self.assertFalse(self.cafe.is_open_at(at(2026, 10, 7, 19)))

    def test_uses_cafe_timezone_not_utc(self):
        # 05:00 UTC is 08:00 in Nairobi: open.
        moment = dt.datetime(2026, 10, 7, 5, 0, tzinfo=dt.UTC)
        self.assertTrue(self.cafe.is_open_at(moment))

    def test_day_marked_closed(self):
        OpeningHours.objects.filter(cafe=self.cafe, weekday=6).update(is_closed=True, opens=None, closes=None)
        self.assertFalse(self.cafe.is_open_at(at(2026, 10, 11, 12)))  # Sunday

    def test_one_off_closure(self):
        Closure.objects.create(cafe=self.cafe, date=dt.date(2026, 10, 20), note="Mashujaa Day")
        self.assertFalse(self.cafe.is_open_at(at(2026, 10, 20, 12)))

    def test_hours_past_midnight(self):
        set_hours(self.cafe, dt.time(18), dt.time(1), days=[4])  # Friday 6 PM – 1 AM
        self.assertTrue(self.cafe.is_open_at(at(2026, 10, 9, 23)))  # Friday 11 PM
        self.assertTrue(self.cafe.is_open_at(at(2026, 10, 10, 0, 30)))  # Saturday 00:30
        self.assertFalse(self.cafe.is_open_at(at(2026, 10, 9, 17)))

    def test_no_hours_means_closed(self):
        cafe = make_cafe("empty-cafe")
        self.assertFalse(cafe.is_open_at(at(2026, 10, 7, 12)))


class ValidationTests(TestCase):
    def test_reserved_slug_rejected(self):
        cafe = Cafe(name="Dash", slug="dashboard")
        with self.assertRaises(ValidationError):
            cafe.full_clean()

    def test_bad_brand_colour_rejected(self):
        cafe = Cafe(name="X", slug="x", brand_colour="red")
        with self.assertRaises(ValidationError):
            cafe.full_clean()

    def test_open_day_needs_times_at_database_level(self):
        cafe = make_cafe()
        with self.assertRaises(IntegrityError):
            OpeningHours.objects.create(cafe=cafe, weekday=0, is_closed=False)

    def test_same_open_and_close_rejected(self):
        hours = OpeningHours(cafe=make_cafe(), weekday=0, opens=dt.time(9), closes=dt.time(9))
        with self.assertRaises(ValidationError):
            hours.clean()


class MoneyFilterTests(TestCase):
    def test_formats(self):
        cafe = Cafe(currency="KES")
        self.assertEqual(money(Decimal("250.00"), cafe), "KES 250")
        self.assertEqual(money(Decimal("1250.50"), cafe), "KES 1,250.50")
