"""Messages from the contact page, and the list of customers who signed up."""

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from customers.models import Customer, Enquiry

from .access import cafe_access


@cafe_access()
def inbox(request):
    show = "done" if request.GET.get("show") == "done" else "open"
    enquiries = Enquiry.objects.filter(cafe=request.cafe).select_related("customer", "resolved_by")
    if show == "done":
        enquiries = enquiries.filter(status=Enquiry.Status.RESOLVED).order_by("-resolved_at")[:50]
    else:
        enquiries = enquiries.filter(status=Enquiry.Status.NEW).order_by("created_at")
    open_count = Enquiry.objects.filter(cafe=request.cafe, status=Enquiry.Status.NEW).count()
    return render(request, "dashboard/inbox.html", {"enquiries": enquiries, "show": show, "open_count": open_count})


@require_POST
@cafe_access()
def enquiry_resolve(request, pk):
    enquiry = get_object_or_404(Enquiry, pk=pk, cafe=request.cafe)
    if request.POST.get("action") == "reopen":
        enquiry.status = Enquiry.Status.NEW
        enquiry.resolved_by = None
        enquiry.resolved_at = None
        messages.info(request, f"Message from {enquiry.name} moved back to open.")
    else:
        enquiry.status = Enquiry.Status.RESOLVED
        enquiry.staff_note = request.POST.get("staff_note", "").strip()[:500]
        enquiry.resolved_by = request.user
        enquiry.resolved_at = timezone.now()
        messages.success(request, f"Message from {enquiry.name} marked as dealt with.")
    enquiry.save()
    return redirect("dashboard:inbox", cafe_slug=request.cafe.slug)


@cafe_access(owner_only=True)
def customers(request):
    people = Customer.objects.filter(cafe=request.cafe).annotate(order_count=Count("orders"))
    return render(
        request,
        "dashboard/customers.html",
        {"customers": people, "news_count": sum(c.wants_news for c in people)},
    )
