from django.db import models


class BudgetWindow(models.Model):
    """Esqueleto da janela semanal de orçamento de tokens (RF-11..13).

    Reserva o formato dos dados; o Token Budget Scheduler funcional
    (pausa automática, fila noturna, projeção de esgotamento) entra em
    fase posterior.
    """

    # Início da semana à qual esta janela se refere.
    week_start = models.DateField(unique=True)

    quota_total = models.BigIntegerField(default=0)
    used = models.BigIntegerField(default=0)
    # Reserva pessoal protegida, subtraída do disponível para automação.
    personal_reserve = models.BigIntegerField(default=0)
    # Limiar (%) que pausa a fila de baixa prioridade (padrão 85%).
    pause_threshold_pct = models.PositiveSmallIntegerField(default=85)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]

    def __str__(self):
        return f"Semana {self.week_start}"
