"""Dashboard pages for running the café: the till, reports, clock in/out, timesheets and the team."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cafes.models import MenuCategory, MenuItem, StaffMembership
from cafes.templatetags.cafe_tags import money
from operations import reports, services
from operations.models import Sale

from .access import cafe_access
from .forms import StaffForm


def _period(request):
    key = request.GET.get("period", "7")
    return key if key in reports.PERIODS else "7"


# --- Till -----------------------------------------------------------------


@cafe_access()
def till(request):
    cafe = request.cafe
    if request.method == "POST":
        quantities = {}
        for key, value in request.POST.items():
            if key.startswith("qty_") and value.strip():
                try:
                    quantities[key[4:]] = int(value)
                except ValueError:
                    continue
        try:
            sale = services.record_sale(cafe, request.user, quantities, request.POST.get("payment_method", ""))
        except ValidationError as error:
            messages.error(request, error.messages[0])
        except ValueError:
            messages.error(request, "Check the quantities and try again.")
        else:
            messages.success(request, f"Sale recorded: {money(sale.total, cafe)}.")
        return redirect("dashboard:till", cafe_slug=cafe.slug)

    categories = MenuCategory.objects.filter(cafe=cafe).prefetch_related(
        Prefetch("items", queryset=MenuItem.objects.filter(is_available=True).order_by("position", "id"))
    )
    today_start, _ = reports.period_bounds(cafe, "today")[2:]
    recent = (
        Sale.objects.filter(cafe=cafe, sold_at__gte=today_start)
        .select_related("recorded_by")
        .prefetch_related("lines")[:15]
    )
    return render(
        request,
        "dashboard/till.html",
        {"categories": categories, "recent": recent, "payment_methods": Sale.PaymentMethod.choices},
    )


@require_POST
@cafe_access(owner_only=True)
def sale_void(request, pk):
    sale = get_object_or_404(Sale, pk=pk, cafe=request.cafe)
    services.void_sale(sale, request.user)
    messages.success(request, "Sale cancelled. It no longer counts in your reports.")
    back = "dashboard:reports" if request.POST.get("next") == "reports" else "dashboard:till"
    return redirect(back, cafe_slug=request.cafe.slug)


# --- Reports (owners) -----------------------------------------------------


@cafe_access(owner_only=True)
def sales_reports(request):
    key = _period(request)
    report = reports.sales_report(request.cafe, key)
    peak_day = max((d["revenue"] for d in report["days"]), default=0) or 1
    peak_hour = max((h["sales"] for h in report["busy_hours"]), default=0) or 1
    top_quantity = max((b["quantity"] for b in report["best_sellers"]), default=0) or 1
    missing_costs = MenuItem.objects.filter(category__cafe=request.cafe, cost__isnull=True).count()
    return render(
        request,
        "dashboard/reports.html",
        {
            "report": report,
            "period": key,
            "periods": reports.PERIODS,
            "peak_day": peak_day,
            "peak_hour": peak_hour,
            "top_quantity": top_quantity,
            "missing_costs": missing_costs,
        },
    )


# --- Clock in / out (everyone) -----------------------------------------------


@cafe_access()
def clock(request):
    shift = services.open_shift(request.cafe, request.user)
    recent = request.user.shifts.filter(cafe=request.cafe).select_related("cafe")[:5]
    return render(request, "dashboard/clock.html", {"shift": shift, "recent": recent})


@require_POST
@cafe_access()
def clock_action(request):
    action = request.POST.get("action")
    lat, lng, accuracy = request.POST.get("lat"), request.POST.get("lng"), request.POST.get("accuracy")
    try:
        if action == "in":
            shift = services.clock_in(request.cafe, request.user, lat, lng, accuracy)
            text = f"Clocked in at {shift.clock_in_at.astimezone(request.cafe.tz):%H:%M}."
            if shift.clock_in_outside:
                text += " You seem to be away from the café, so your manager will see a note on this shift."
            messages.success(request, text)
        elif action == "out":
            shift = services.clock_out(request.cafe, request.user, lat, lng, accuracy)
            hours, minutes = divmod(round(shift.duration.total_seconds() / 60), 60)
            messages.success(request, f"Clocked out. Shift length: {hours} h {minutes} min.")
        else:
            messages.error(request, "Something went wrong. Please try again.")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect("dashboard:clock", cafe_slug=request.cafe.slug)


# --- Timesheets (owners) --------------------------------------------------


@cafe_access(owner_only=True)
def shifts(request):
    key = _period(request)
    data = reports.timesheet(request.cafe, key)
    on_shift = (
        request.cafe.shifts.filter(clock_out_at__isnull=True).select_related("user", "cafe").order_by("clock_in_at")
    )
    return render(
        request,
        "dashboard/shifts.html",
        {**data, "period": key, "periods": reports.PERIODS, "on_shift": on_shift},
    )


# --- Team (owners) --------------------------------------------------------


@cafe_access(owner_only=True)
def team(request):
    form = StaffForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = get_user_model().objects.create_user(
                form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                first_name=form.cleaned_data["first_name"],
            )
            StaffMembership.objects.create(user=user, cafe=request.cafe, role=form.cleaned_data["role"])
        messages.success(
            request,
            f"Added {user.first_name}. They log in at /dashboard/ with the username “{user.username}”.",
        )
        return redirect("dashboard:team", cafe_slug=request.cafe.slug)
    members = request.cafe.memberships.select_related("user").order_by("role", "user__first_name")
    return render(request, "dashboard/team.html", {"form": form, "members": members})


@require_POST
@cafe_access(owner_only=True)
def team_remove(request, pk):
    membership = get_object_or_404(StaffMembership, pk=pk, cafe=request.cafe)
    if membership.user_id == request.user.id:
        messages.error(request, "You can't remove yourself.")
    else:
        name = membership.user.first_name or membership.user.username
        user = membership.user
        membership.delete()
        # A login that no longer works anywhere is switched off rather than deleted, so their
        # past sales and shifts keep their name.
        if not user.memberships.exists() and not user.is_superuser:
            user.is_active = False
            user.save(update_fields=["is_active"])
        messages.success(request, f"{name} can no longer log in to this café.")
    return redirect("dashboard:team", cafe_slug=request.cafe.slug)
