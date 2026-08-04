from django.urls import path

from . import views

urlpatterns = [
    path("", views.healthz, name="healthz"),
]
