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

# Na faixa de atenção, só projetos com peso a partir daqui saem na fila
# noturna (RF-13) — os demais esperam a próxima noite ou o reset.
HIGH_PRIORITY_WEIGHT = 4


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


def cache_tokens(start, end) -> dict:
    """Tokens de prompt lidos e gravados no cache na janela (RF-22).

    `read` é a economia de fato: tokens que entraram no contexto sem serem
    cobrados como entrada nova. Zero significa que o cache não está pegando.
    """
    row = TaskRunStep.objects.filter(created_at__gte=start, created_at__lt=end).aggregate(
        read=Sum("cache_read_tokens"), written=Sum("cache_write_tokens")
    )
    return {"read": row["read"] or 0, "written": row["written"] or 0}


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


# Nomes usados na projeção — `weekday()` do Python, 0=segunda.
_WEEKDAYS = [
    "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo",
]


def _period_of_day(hour: int) -> str:
    if hour < 6:
        return "de madrugada"
    if hour < 12:
        return "de manhã"
    if hour < 18:
        return "à tarde"
    return "à noite"


def projection(used, quota, start, end, now=None, reserve_pct: int = 0) -> str:
    """Frase de projeção de esgotamento da cota (RF-11).

    Extrapola o ritmo da janela corrente (`used / tempo decorrido`). Se nesse
    ritmo a cota atravessa o reset, diz que sobra; senão, nomeia quando acaba.
    Devolve vazio quando não há base para projetar — sem cota configurada, sem
    consumo, ou janela recém-começada (extrapolar os primeiros minutos daria
    um número sem sentido).
    """
    now = now or timezone.now()
    if quota <= 0 or used <= 0:
        return ""

    elapsed = (now - start).total_seconds()
    if elapsed < 3600:  # menos de uma hora de janela: amostra pequena demais
        return ""

    remaining = Decimal(quota) - Decimal(used)
    if remaining <= 0:
        return "A cota semanal já foi consumida por inteiro."

    # Quanto ainda dá para gastar antes de encostar na reserva pessoal.
    reserve = Decimal(quota) * Decimal(reserve_pct) / Decimal(100)
    if reserve > 0 and remaining <= reserve:
        pct_left = float(remaining / Decimal(quota) * 100)
        return f"Restam {pct_left:.0f}% antes da reserva pessoal."

    burn_per_second = Decimal(used) / Decimal(elapsed)
    seconds_left = float(remaining / burn_per_second)
    exhausted_at = now + timedelta(seconds=seconds_left)

    if exhausted_at >= end:
        return "No ritmo atual, sobra cota até o reset."

    dia = _WEEKDAYS[exhausted_at.weekday()]
    periodo = _period_of_day(exhausted_at.hour)
    return f"No ritmo atual, a cota acaba {dia} {periodo}."


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
        # Descreve o que de fato acontece nesta faixa (RF-13): a fila noturna
        # passa a despachar só os projetos de peso alto.
        warn_text = (
            f"Ritmo acima do previsto — a fila noturna vai priorizar os projetos "
            f"de peso {HIGH_PRIORITY_WEIGHT} e acima."
        )
    else:
        warn_text = ""

    return {
        "quota_total_usd": quota,
        "used_usd": used,
        "pct": round(pct, 1),
        "color": color,
        "warn": warn,
        "warn_text": warn_text,
        "projection": projection(
            used, quota, start, end, reserve_pct=settings_obj.personal_reserve_pct
        ),
        "should_pause_nightly": should_pause_nightly,
        # A fila noturna corta por peso nesta faixa (RF-13) — o frontend usa
        # isso para marcar quais projetos passam.
        "prioritizing_by_weight": color == "atencao",
        "high_priority_weight": HIGH_PRIORITY_WEIGHT,
        "cache_tokens": cache_tokens(start, end),
        "personal_reserve_pct": settings_obj.personal_reserve_pct,
        "pause_threshold_pct": settings_obj.pause_threshold_pct,
        "window_start": start.isoformat(),
        "reset_at": end.isoformat(),
    }
