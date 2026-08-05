from django.contrib import admin

from .models import BudgetSettings


@admin.register(BudgetSettings)
class BudgetSettingsAdmin(admin.ModelAdmin):
    list_display = ("quota_total_usd", "personal_reserve_pct", "pause_threshold_pct", "reset_weekday", "reset_hour")

    def has_add_permission(self, request):
        # Singleton — só existe a linha pk=1, criada sob demanda por load().
        return not BudgetSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
