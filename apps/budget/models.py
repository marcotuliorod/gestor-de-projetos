from django.db import models


class BudgetSettings(models.Model):
    """Configuração única do orçamento semanal de agentes (RF-11..13).

    Singleton (sempre `pk=1`) — o uso real é computado sob demanda a partir
    de `TaskRunStep.cost_usd` (ver apps.budget.tracking), não guardado aqui.
    """

    quota_total_usd = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # Fatia protegida do orçamento (informativa na UI — o gate de pausa em
    # si usa só pause_threshold_pct).
    personal_reserve_pct = models.PositiveSmallIntegerField(default=15)
    # Limiar (%) que pausa a fila noturna (RF-12).
    pause_threshold_pct = models.PositiveSmallIntegerField(default=85)
    # Dia/hora em que a semana orçamentária reinicia (0=segunda..6=domingo).
    reset_weekday = models.PositiveSmallIntegerField(default=1)
    reset_hour = models.PositiveSmallIntegerField(default=9)

    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "BudgetSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Orçamento semanal: ${self.quota_total_usd}"
