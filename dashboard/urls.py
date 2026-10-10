from django.contrib.auth import views as auth_views
from django.urls import path

from . import views, views_ops, views_orders

app_name = "dashboard"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "password/",
        auth_views.PasswordChangeView.as_view(
            template_name="dashboard/form.html",
            extra_context={"title": "Change password"},
            success_url="/dashboard/password/done/",
        ),
        name="password_change",
    ),
    path(
        "password/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="dashboard/password_done.html"),
        name="password_change_done",
    ),
    path("", views.home, name="home"),
    path("<slug:cafe_slug>/", views.overview, name="overview"),
    path("<slug:cafe_slug>/menu/", views.menu, name="menu"),
    path("<slug:cafe_slug>/menu/sections/new/", views.category_edit, name="category_add"),
    path("<slug:cafe_slug>/menu/sections/<int:pk>/", views.category_edit, name="category_edit"),
    path("<slug:cafe_slug>/menu/sections/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("<slug:cafe_slug>/menu/items/new/", views.item_edit, name="item_add"),
    path("<slug:cafe_slug>/menu/items/<int:pk>/", views.item_edit, name="item_edit"),
    path("<slug:cafe_slug>/menu/items/<int:pk>/delete/", views.item_delete, name="item_delete"),
    path("<slug:cafe_slug>/menu/items/<int:pk>/toggle/", views.item_toggle, name="item_toggle"),
    path("<slug:cafe_slug>/hours/", views.hours, name="hours"),
    path("<slug:cafe_slug>/hours/closures/", views.closure_add, name="closure_add"),
    path("<slug:cafe_slug>/hours/closures/<int:pk>/delete/", views.closure_delete, name="closure_delete"),
    path("<slug:cafe_slug>/settings/", views.cafe_settings, name="settings"),
    path("<slug:cafe_slug>/orders/", views_orders.orders, name="orders"),
    path("<slug:cafe_slug>/orders/<int:pk>/status/", views_orders.order_status, name="order_status"),
    path("<slug:cafe_slug>/till/", views_ops.till, name="till"),
    path("<slug:cafe_slug>/sales/<int:pk>/void/", views_ops.sale_void, name="sale_void"),
    path("<slug:cafe_slug>/reports/", views_ops.sales_reports, name="reports"),
    path("<slug:cafe_slug>/clock/", views_ops.clock, name="clock"),
    path("<slug:cafe_slug>/clock/action/", views_ops.clock_action, name="clock_action"),
    path("<slug:cafe_slug>/shifts/", views_ops.shifts, name="shifts"),
    path("<slug:cafe_slug>/team/", views_ops.team, name="team"),
    path("<slug:cafe_slug>/team/<int:pk>/remove/", views_ops.team_remove, name="team_remove"),
]
