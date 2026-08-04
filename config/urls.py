from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", include("apps.core.urls")),
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.status.urls")),
]
