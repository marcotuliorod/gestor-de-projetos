"""Roteamento de modelo por fase (RF-18/19/20 — seção 8 do PRD).

Função pura, sem I/O — fácil de testar isoladamente.
"""

from apps.projects.models import Project

from .models import TaskRunStep

Phase = TaskRunStep.Phase

# Tabela de roteamento para o modo AUTO. Discuss/Verify/Ship são passos
# baratos (leitura/checagem); Plan/Execute são onde o trabalho pesado
# acontece e por isso partem de Sonnet.
_AUTO_ROUTING = {
    Phase.DISCUSS: Project.Model.HAIKU,
    Phase.PLAN: Project.Model.SONNET,
    Phase.EXECUTE: Project.Model.SONNET,
    Phase.VERIFY: Project.Model.HAIKU,
    Phase.SHIP: Project.Model.HAIKU,
}

# Fases que escalam para Opus quando Verify falha repetidamente — Verify em
# si não escala (é o checador, não quem produz o trabalho que falhou).
_ESCALATABLE_PHASES = {Phase.PLAN, Phase.EXECUTE}

ESCALATION_THRESHOLD = 2


def choose_model(project: Project, phase: str, consecutive_verify_failures: int) -> str:
    """Decide o modelo para uma fase de um TaskRun.

    Override manual do projeto (`default_model != AUTO`) sempre vence e não
    participa do escalonamento automático — se o usuário fixou um modelo,
    não gastamos Opus às escondidas por trás dele.
    """
    if project.default_model != Project.Model.AUTO:
        return project.default_model

    base = _AUTO_ROUTING[phase]
    if phase in _ESCALATABLE_PHASES and consecutive_verify_failures >= ESCALATION_THRESHOLD:
        return Project.Model.OPUS
    return base
