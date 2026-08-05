"""Agregação de custo real de agentes por janela semanal (RF-11..13).

Funções puras — nenhum estado é persistido além do que já existe em
`TaskRunStep.cost_usd`; qualquer janela (atual ou passada) é só uma soma
sob demanda. Evita job de "virar a semana" e contador que pode dessincronizar.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.agents.models import TaskRunStep

from .models import BudgetSettings

# Abaixo deste percentual, o estado é "normal". Entre isto e
# pause_threshold_pct, "atenção". A partir de pause_threshold_pct, "crítico"
# (e a fila noturna pausa).
WARNING_THRESHOLD_PCT = 70


def current_window_bounds(now=None, settings_obj=None):
    """Início/fim da janela orçamentária corrente, a partir de
    `reset_weekday`/`reset_hour` configurados."""
    now = now or timezone.now()
    settings_obj = settings_obj or BudgetSettings.load()

    candidate = now.replace(hour=settings_obj.reset_hour, minute=0, second=0, microsecond=0)
    days_since = (candidate.weekday() - settings_obj.reset_weekday) % 7
    candidate -= timedelta(days=days_since)
    if candidate > now:
        candidate -= timedelta(days=7)

    start = candidate
    end = start + timedelta(days=7)
    return start, end


def usage_usd(start, end) -> Decimal:
    total = TaskRunStep.objects.filter(
        created_at__gte=start, created_at__lt=end, cost_usd__isnull=False
    ).aggregate(total=Sum("cost_usd"))["total"]
    return total or Decimal("0")


def usage_by_project(start, end) -> dict:
    """Mapa project_id -> custo (USD) na janela, para a distribuição por
    projeto da tela de Cota."""
    rows = (
        TaskRunStep.objects.filter(created_at__gte=start, created_at__lt=end, cost_usd__isnull=False)
        .values("task_run__project_id")
        .annotate(total=Sum("cost_usd"))
    )
    return {row["task_run__project_id"]: row["total"] for row in rows}


def weekly_history(n=6) -> list[dict]:
    """Últimas `n` janelas (mais antiga primeiro), cada uma com o custo
    somado — sem precisar de nenhum dado persistido além dos TaskRunSteps."""
    start, _ = current_window_bounds()
    weeks = []
    for i in range(n):
        w_start = start - timedelta(days=7 * i)
        w_end = w_start + timedelta(days=7)
        weeks.append({"week_start": w_start.date().isoformat(), "used_usd": usage_usd(w_start, w_end)})
    weeks.reverse()
    return weeks


def budget_state() -> dict:
    """Estado agregado consumido pela API/tela de Cota: uso atual, cor,
    aviso, e se a fila noturna deve pausar (RF-12)."""
    settings_obj = BudgetSettings.load()
    start, end = current_window_bounds(settings_obj=settings_obj)
    used = usage_usd(start, end)
    quota = settings_obj.quota_total_usd

    pct = float(used / quota * 100) if quota > 0 else 0.0

    if pct >= settings_obj.pause_threshold_pct:
        color = "critico"
    elif pct >= WARNING_THRESHOLD_PCT:
        color = "atencao"
    else:
        color = "normal"

    should_pause_nightly = pct >= settings_obj.pause_threshold_pct
    warn = color != "normal"
    if color == "critico":
        warn_text = (
            'Fila noturna pausada automaticamente até o próximo reset. '
            'Só tarefas marcadas como "Agora" vão rodar.'
        )
    elif color == "atencao":
        warn_text = "Ritmo acima do previsto — perto do limiar que pausa a fila noturna."
    else:
        warn_text = ""

    return {
        "quota_total_usd": quota,
        "used_usd": used,
        "pct": round(pct, 1),
        "color": color,
        "warn": warn,
        "warn_text": warn_text,
        "should_pause_nightly": should_pause_nightly,
        "personal_reserve_pct": settings_obj.personal_reserve_pct,
        "pause_threshold_pct": settings_obj.pause_threshold_pct,
        "window_start": start.isoformat(),
        "reset_at": end.isoformat(),
    }
