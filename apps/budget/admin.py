from django.contrib import admin

from .models import BudgetWindow


@admin.register(BudgetWindow)
class BudgetWindowAdmin(admin.ModelAdmin):
    list_display = ("week_start", "quota_total", "used", "personal_reserve", "pause_threshold_pct")
