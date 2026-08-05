from rest_framework import serializers

from .models import BudgetSettings


class BudgetSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetSettings
        fields = ["quota_total_usd", "personal_reserve_pct", "pause_threshold_pct"]
