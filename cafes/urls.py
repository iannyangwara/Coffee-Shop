from django.urls import path

from . import views

app_name = "cafes"

urlpatterns = [
    path("<slug:cafe_slug>/", views.cafe_home, name="home"),
    path("<slug:cafe_slug>/menu/", views.cafe_menu, name="menu"),
    path("<slug:cafe_slug>/visit/", views.cafe_visit, name="visit"),
]
