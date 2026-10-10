from django.contrib import admin

from .models import Order, OrderLine


class OrderLineInline(admin.TabularInline):
    model = OrderLine
    extra = 0
    readonly_fields = ["menu_item", "name", "quantity", "unit_price", "unit_cost", "sugar", "note"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["code", "cafe", "customer_name", "status", "total", "created_at"]
    list_filter = ["cafe", "status"]
    search_fields = ["code", "customer_name", "customer_phone"]
    date_hierarchy = "created_at"
    readonly_fields = ["token", "total", "sale"]
    inlines = [OrderLineInline]
