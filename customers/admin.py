from django.contrib import admin

from .models import Customer, Enquiry


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "cafe", "wants_news", "created_at"]
    list_filter = ["cafe", "wants_news"]
    search_fields = ["name", "email", "phone"]
    exclude = ["password"]
    readonly_fields = ["created_at", "last_login_at"]


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "cafe", "status", "created_at"]
    list_filter = ["cafe", "kind", "status"]
    search_fields = ["name", "email", "phone", "message", "order_code"]
    date_hierarchy = "created_at"
