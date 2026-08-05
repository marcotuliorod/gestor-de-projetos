from django.contrib import admin
from django.urls import include, path

from apps.status.webhook_views import github_webhook

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", include("apps.core.urls")),
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.status.urls")),
    path("api/", include("apps.agents.urls")),
    path("api/", include("apps.budget.urls")),
    path("api/webhooks/github/", github_webhook, name="github-webhook"),
]
