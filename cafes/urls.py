from django.urls import path

from customers import views as customer_views
from ordering import views as ordering_views

from . import views

app_name = "cafes"

urlpatterns = [
    path("<slug:cafe_slug>/", views.cafe_home, name="home"),
    path("<slug:cafe_slug>/menu/", views.cafe_menu, name="menu"),
    path("<slug:cafe_slug>/visit/", views.cafe_visit, name="visit"),
    path("<slug:cafe_slug>/menu/<int:item_id>/", ordering_views.item_detail, name="item"),
    path("<slug:cafe_slug>/basket/", ordering_views.basket, name="basket"),
    path("<slug:cafe_slug>/basket/update/", ordering_views.basket_update, name="basket_update"),
    path("<slug:cafe_slug>/order/<uuid:token>/", ordering_views.order_status, name="order_status"),
    path("<slug:cafe_slug>/contact/", customer_views.contact, name="contact"),
    path("<slug:cafe_slug>/contact/sent/", customer_views.contact_sent, name="contact_sent"),
    path("<slug:cafe_slug>/sign-up/", customer_views.sign_up, name="sign_up"),
    path("<slug:cafe_slug>/sign-in/", customer_views.sign_in, name="sign_in"),
    path("<slug:cafe_slug>/sign-out/", customer_views.sign_out, name="sign_out"),
    path("<slug:cafe_slug>/account/", customer_views.account, name="account"),
]
