from django.contrib import admin

from .models import Cafe, Closure, MenuCategory, MenuItem, OpeningHours, StaffMembership


class OpeningHoursInline(admin.TabularInline):
    model = OpeningHours
    extra = 0


class StaffInline(admin.TabularInline):
    model = StaffMembership
    extra = 1
    autocomplete_fields = ["user"]


@admin.register(Cafe)
class CafeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "town", "is_published", "created_at"]
    list_filter = ["is_published", "town"]
    search_fields = ["name", "slug", "town"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [StaffInline, OpeningHoursInline]


class MenuItemInline(admin.TabularInline):
    model = MenuItem
    extra = 0
    fields = ["name", "price", "is_available", "is_featured", "position"]


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "cafe", "position"]
    list_filter = ["cafe"]
    inlines = [MenuItemInline]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "is_available", "is_featured"]
    list_filter = ["category__cafe", "is_available"]
    search_fields = ["name"]


admin.site.register(Closure)
admin.site.register(StaffMembership)
