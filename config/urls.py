from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from cafes.views import platform_home

admin.site.site_header = "Café platform admin"

urlpatterns = [
    path("healthz", lambda request: HttpResponse("ok"), name="healthz"),
    path("admin/", admin.site.urls),
    path("dashboard/", include("dashboard.urls")),
    path("", platform_home, name="platform_home"),
    # Café sites last: /<cafe-slug>/... (platform paths above are reserved slugs)
    path("", include("cafes.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
