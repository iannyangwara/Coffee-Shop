"""The customer side: the contact page, and signing up, in and out of a café's website."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from cafes.views import _base_context, _published_cafe
from dashboard import throttle

from . import services
from .forms import AccountForm, EnquiryForm, SignInForm, SignUpForm
from .models import Customer

# Checked against when nobody has that email, so a wrong email takes as long as a wrong password.
_DUMMY_HASH = make_password("not-a-real-password")


def _next_url(request, cafe):
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
        return target
    return cafe.get_absolute_url()


def contact(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    customer = services.current_customer(request, cafe)
    initial = {"kind": request.GET.get("about", "question")}
    if customer:
        initial |= {"name": customer.name, "email": customer.email, "phone": customer.phone}
    form = EnquiryForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["website"]:
            # A bot filled in the hidden box: pretend it worked and keep nothing.
            return redirect("cafes:contact_sent", cafe_slug=cafe.slug)
        if services.too_many(request, cafe, "contact"):
            form.add_error(None, "You've sent several messages already. Please call us if it's urgent.")
        else:
            enquiry = form.save(commit=False)
            enquiry.cafe = cafe
            enquiry.customer = customer
            enquiry.save()
            services.count_use(request, cafe, "contact")
            return redirect("cafes:contact_sent", cafe_slug=cafe.slug)
    return render(request, "customers/contact.html", {**_base_context(request, cafe), "form": form})


def contact_sent(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    return render(request, "customers/contact_sent.html", _base_context(request, cafe))


def sign_up(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    if services.current_customer(request, cafe):
        return redirect("cafes:account", cafe_slug=cafe.slug)
    form = SignUpForm(request.POST or None, cafe=cafe)
    if request.method == "POST" and form.is_valid():
        if services.too_many(request, cafe, "sign-up"):
            form.add_error(None, "Too many new accounts from here. Please try again later.")
        else:
            customer = form.save()
            services.count_use(request, cafe, "sign-up")
            services.log_in(request, customer)
            messages.success(request, f"Welcome, {customer.name.split()[0]}! Your account is ready.")
            return redirect(_next_url(request, cafe))
    context = {**_base_context(request, cafe), "form": form, "next": _next_url(request, cafe)}
    return render(request, "customers/sign_up.html", context)


def sign_in(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    if services.current_customer(request, cafe):
        return redirect("cafes:account", cafe_slug=cafe.slug)
    form = SignInForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        throttle_name = f"customer:{cafe.pk}:{email}"
        if throttle.is_locked(request, throttle_name):
            minutes = settings.LOGIN_LOCKOUT_SECONDS // 60
            form.add_error(None, f"Too many attempts. Please wait {minutes} minutes and try again.")
        else:
            customer = Customer.objects.filter(cafe=cafe, email__iexact=email).first()
            if customer and customer.check_password(form.cleaned_data["password"]):
                throttle.clear(request, throttle_name)
                services.log_in(request, customer)
                messages.success(request, f"Welcome back, {customer.name.split()[0]}.")
                return redirect(_next_url(request, cafe))
            if customer is None:
                check_password(form.cleaned_data["password"], _DUMMY_HASH)
            throttle.record_failure(request, throttle_name)
            form.add_error(None, "That email and password don't match an account here.")
    context = {**_base_context(request, cafe), "form": form, "next": _next_url(request, cafe)}
    return render(request, "customers/sign_in.html", context)


@require_POST
def sign_out(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    services.log_out(request, cafe)
    messages.success(request, "You're signed out.")
    return redirect(cafe.get_absolute_url())


def account(request, cafe_slug):
    cafe = _published_cafe(cafe_slug)
    customer = services.current_customer(request, cafe)
    if customer is None:
        return redirect(f"{cafe.get_absolute_url()}sign-in/?next={request.path}")
    form = AccountForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your details are saved.")
        return redirect("cafes:account", cafe_slug=cafe.slug)
    with timezone.override(cafe.tz):
        return render(
            request,
            "customers/account.html",
            {
                **_base_context(request, cafe),
                "form": form,
                "orders": customer.orders.prefetch_related("lines")[:10],
                "enquiries": customer.enquiries.all()[:10],
            },
        )
