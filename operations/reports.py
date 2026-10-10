"""Numbers for the owner's reports: sales, profit, best sellers and busy hours."""

import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import ExtractHour, TruncDate

from .models import Sale, SaleLine, Shift

PERIODS = {"today": ("Today", 1), "7": ("7 days", 7), "30": ("30 days", 30), "90": ("90 days", 90)}


def period_bounds(cafe, key):
    """Start and end (aware datetimes) of a period ending today, in the café's own timezone."""
    _, days = PERIODS[key]
    today = cafe.local_now().date()
    start_date = today - dt.timedelta(days=days - 1)
    start = dt.datetime.combine(start_date, dt.time.min, tzinfo=cafe.tz)
    end = dt.datetime.combine(today + dt.timedelta(days=1), dt.time.min, tzinfo=cafe.tz)
    return start_date, today, start, end


def sales_report(cafe, key):
    start_date, end_date, start, end = period_bounds(cafe, key)
    sales = Sale.objects.valid().filter(cafe=cafe, sold_at__gte=start, sold_at__lt=end)
    totals = sales.aggregate(revenue=Sum("total"), cost=Sum("cost_total"), count=Count("id"))
    revenue = totals["revenue"] or Decimal("0")
    count = totals["count"] or 0

    lines = SaleLine.objects.filter(sale__in=sales)
    # Profit only counts lines whose cost is known, so missing costs never look like pure profit.
    costed = lines.filter(unit_cost__isnull=False).aggregate(
        revenue=Sum(F("unit_price") * F("quantity")), cost=Sum(F("unit_cost") * F("quantity"))
    )
    costed_revenue = costed["revenue"] or Decimal("0")
    profit = costed_revenue - (costed["cost"] or Decimal("0"))
    uncosted_revenue = revenue - costed_revenue

    # Daily revenue, filling in days with no sales so the chart has no gaps.
    by_day = {
        row["day"]: row["revenue"]
        for row in sales.annotate(day=TruncDate("sold_at", tzinfo=cafe.tz)).values("day").annotate(revenue=Sum("total"))
    }
    days = []
    d = start_date
    while d <= end_date:
        days.append({"date": d, "revenue": by_day.get(d, Decimal("0"))})
        d += dt.timedelta(days=1)

    best_sellers = [
        {"name": row["name"], "quantity": row["sold"], "revenue": row["revenue"], "profit": row["profit"]}
        for row in lines.values("name")
        .annotate(
            sold=Sum("quantity"),
            revenue=Sum(F("unit_price") * F("quantity")),
            profit=Sum((F("unit_price") - F("unit_cost")) * F("quantity"), filter=Q(unit_cost__isnull=False)),
        )
        .order_by("-sold", "-revenue")[:10]
    ]

    hours = defaultdict(int)
    for row in sales.annotate(hour=ExtractHour("sold_at", tzinfo=cafe.tz)).values("hour").annotate(n=Count("id")):
        hours[row["hour"]] = row["n"]
    busy_hours = [{"hour": h, "sales": hours[h]} for h in range(24)]
    # Trim to the hours the café actually trades, plus the edges of any sales outside them.
    active = [h["hour"] for h in busy_hours if h["sales"]]
    if active:
        busy_hours = busy_hours[min(active) : max(active) + 1]

    payments = {
        row["payment_method"]: row
        for row in sales.values("payment_method").annotate(revenue=Sum("total"), count=Count("id"))
    }
    payment_split = [
        {"label": label, "revenue": payments.get(value, {}).get("revenue") or Decimal("0")}
        for value, label in Sale.PaymentMethod.choices
        if value in payments
    ]

    return {
        "period_label": PERIODS[key][0],
        "start_date": start_date,
        "end_date": end_date,
        "revenue": revenue,
        "count": count,
        "average": (revenue / count) if count else Decimal("0"),
        "profit": profit,
        "margin": (profit / costed_revenue * 100) if costed_revenue else None,
        "uncosted_revenue": uncosted_revenue,
        "days": days,
        "best_sellers": best_sellers,
        "busy_hours": busy_hours,
        "payment_split": payment_split,
    }


def timesheet(cafe, key):
    _, _, start, end = period_bounds(cafe, key)
    shifts = list(
        Shift.objects.filter(cafe=cafe, clock_in_at__gte=start, clock_in_at__lt=end)
        .select_related("user", "cafe")
        .order_by("-clock_in_at")
    )
    per_worker = defaultdict(lambda: {"hours": 0.0, "shifts": 0, "flagged": 0})
    for shift in shifts:
        row = per_worker[shift.user]
        row["hours"] += shift.hours
        row["shifts"] += 1
        row["flagged"] += int(shift.flagged)
    workers = sorted(
        ({"user": user, **row} for user, row in per_worker.items()), key=lambda r: r["hours"], reverse=True
    )
    return {"shifts": shifts, "workers": workers}
