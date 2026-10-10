from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cafes.models import Cafe, Closure, MenuCategory, MenuItem, OpeningHours

from . import throttle
from .access import cafe_access
from .forms import CafeSettingsForm, CategoryForm, ClosureForm, MenuItemForm, OpeningHoursFormSet


class LoginView(auth_views.LoginView):
    template_name = "dashboard/login.html"
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")
        if throttle.is_locked(request, username):
            form = self.get_form()
            form.add_error(None, "Too many failed attempts. Please wait 15 minutes and try again.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        throttle.record_failure(self.request, self.request.POST.get("username", ""))
        return super().form_invalid(form)

    def form_valid(self, form):
        throttle.clear(self.request, self.request.POST.get("username", ""))
        return super().form_valid(form)


@login_required
def home(request):
    """Send staff straight to their café; list them if they work at several."""
    if request.user.is_superuser:
        cafes = Cafe.objects.all()
    else:
        cafes = Cafe.objects.filter(memberships__user=request.user)
    cafes = list(cafes)
    if len(cafes) == 1:
        return redirect("dashboard:overview", cafe_slug=cafes[0].slug)
    return render(request, "dashboard/choose_cafe.html", {"cafes": cafes})


@cafe_access()
def overview(request):
    cafe = request.cafe
    items = MenuItem.objects.filter(category__cafe=cafe)
    context = {
        "item_count": items.count(),
        "sold_out": items.filter(is_available=False).select_related("category"),
        "category_count": cafe.menu_categories.count(),
        "is_open": cafe.is_open_now(),
    }
    return render(request, "dashboard/overview.html", context)


# --- Menu -----------------------------------------------------------------


@cafe_access()
def menu(request):
    categories = MenuCategory.objects.filter(cafe=request.cafe).prefetch_related(
        Prefetch("items", queryset=MenuItem.objects.order_by("position", "id"))
    )
    return render(request, "dashboard/menu.html", {"categories": categories})


@cafe_access()
def category_edit(request, pk=None):
    category = get_object_or_404(MenuCategory, pk=pk, cafe=request.cafe) if pk else None
    form = CategoryForm(request.POST or None, instance=category, cafe=request.cafe)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Menu section saved.")
        return redirect("dashboard:menu", cafe_slug=request.cafe.slug)
    return render(
        request, "dashboard/form.html", {"form": form, "title": "Edit section" if category else "New menu section"}
    )


@require_POST
@cafe_access()
def category_delete(request, pk):
    category = get_object_or_404(MenuCategory, pk=pk, cafe=request.cafe)
    if category.items.exists():
        messages.error(request, f"Move or delete the items in “{category.name}” first.")
    else:
        category.delete()
        messages.success(request, "Menu section deleted.")
    return redirect("dashboard:menu", cafe_slug=request.cafe.slug)


@cafe_access()
def item_edit(request, pk=None):
    item = get_object_or_404(MenuItem, pk=pk, category__cafe=request.cafe) if pk else None
    if item is None and not request.cafe.menu_categories.exists():
        messages.info(request, "Add a menu section (like “Hot drinks”) before adding items.")
        return redirect("dashboard:category_add", cafe_slug=request.cafe.slug)
    initial = {}
    if item is None and (category_id := request.GET.get("category")):
        initial["category"] = category_id
    form = MenuItemForm(request.POST or None, request.FILES or None, instance=item, initial=initial, cafe=request.cafe)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"“{form.instance.name}” saved.")
        return redirect("dashboard:menu", cafe_slug=request.cafe.slug)
    return render(
        request, "dashboard/form.html", {"form": form, "title": "Edit item" if item else "New menu item", "item": item}
    )


@require_POST
@cafe_access()
def item_delete(request, pk):
    item = get_object_or_404(MenuItem, pk=pk, category__cafe=request.cafe)
    item.delete()
    messages.success(request, f"“{item.name}” deleted.")
    return redirect("dashboard:menu", cafe_slug=request.cafe.slug)


@require_POST
@cafe_access()
def item_toggle(request, pk):
    """Mark an item sold out / available. Returns just the updated row for HTMX."""
    item = get_object_or_404(MenuItem, pk=pk, category__cafe=request.cafe)
    item.is_available = not item.is_available
    item.save(update_fields=["is_available", "updated_at"])
    if request.headers.get("HX-Request"):
        return render(request, "dashboard/_item_row.html", {"item": item})
    return redirect("dashboard:menu", cafe_slug=request.cafe.slug)


# --- Hours ----------------------------------------------------------------


@cafe_access()
def hours(request):
    cafe = request.cafe
    OpeningHours.objects.bulk_create(
        [OpeningHours(cafe=cafe, weekday=day, is_closed=True) for day in OpeningHours.Weekday.values],
        ignore_conflicts=True,
    )
    queryset = OpeningHours.objects.filter(cafe=cafe).order_by("weekday")
    formset = OpeningHoursFormSet(request.POST or None, queryset=queryset, prefix="hours")
    closure_form = ClosureForm(cafe=cafe, prefix="closure")
    if request.method == "POST" and formset.is_valid():
        formset.save()
        messages.success(request, "Opening hours saved.")
        return redirect("dashboard:hours", cafe_slug=cafe.slug)
    upcoming = Closure.objects.filter(cafe=cafe, date__gte=cafe.local_now().date())
    return render(
        request, "dashboard/hours.html", {"formset": formset, "closure_form": closure_form, "closures": upcoming}
    )


@require_POST
@cafe_access()
def closure_add(request):
    form = ClosureForm(request.POST, cafe=request.cafe, prefix="closure")
    if form.is_valid():
        form.save()
        messages.success(request, "Closure added.")
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return redirect("dashboard:hours", cafe_slug=request.cafe.slug)


@require_POST
@cafe_access()
def closure_delete(request, pk):
    get_object_or_404(Closure, pk=pk, cafe=request.cafe).delete()
    messages.success(request, "Closure removed.")
    return redirect("dashboard:hours", cafe_slug=request.cafe.slug)


# --- Settings (owners only) ----------------------------------------------


@cafe_access(owner_only=True)
def cafe_settings(request):
    form = CafeSettingsForm(request.POST or None, request.FILES or None, instance=request.cafe)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Café details saved.")
        return redirect("dashboard:settings", cafe_slug=request.cafe.slug)
    return render(request, "dashboard/form.html", {"form": form, "title": "Café details"})
