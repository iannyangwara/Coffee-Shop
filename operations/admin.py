from django.contrib import admin

from .models import Sale, SaleLine, Shift


class SaleLineInline(admin.TabularInline):
    model = SaleLine
    extra = 0
    readonly_fields = ["menu_item", "name", "quantity", "unit_price", "unit_cost"]
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ["id", "cafe", "sold_at", "total", "payment_method", "recorded_by", "voided_at"]
    list_filter = ["cafe", "payment_method"]
    date_hierarchy = "sold_at"
    readonly_fields = ["total", "cost_total"]
    inlines = [SaleLineInline]


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ["user", "cafe", "clock_in_at", "clock_out_at", "clock_in_distance_m", "clock_out_distance_m"]
    list_filter = ["cafe"]
    date_hierarchy = "clock_in_at"
