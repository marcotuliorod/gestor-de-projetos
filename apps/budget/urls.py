from django.urls import path

from .views import BudgetView

urlpatterns = [
    path("budget/", BudgetView.as_view(), name="budget"),
]
