"""Roteamento de modelo por fase e complexidade (RF-18/19/20 — seção 8 do PRD).

Funções puras, sem I/O — fáceis de testar isoladamente.
"""

import re

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

# Níveis de complexidade estimados a partir da instrução do usuário (RF-18).
SIMPLE, MEDIUM, COMPLEX = 0, 1, 2

# Sinais de trabalho amplo: mexer em arquitetura, migrar, reescrever. A lista
# é curta de propósito — heurística grosseira e legível vale mais aqui do que
# um classificador difícil de prever, porque errar para baixo é barato (o
# escalonamento após falhas de Verify corrige) e errar para cima gasta Opus à
# toa.
_COMPLEX_TERMS = [
    "arquitetura", "arquitetural", "refatorar", "refatoração", "reescrever",
    "redesenhar", "migrar", "migração", "reestruturar", "desacoplar",
    "trade-off", "estratégia", "modelagem",
]

# Sinais de trabalho pontual.
_SIMPLE_TERMS = [
    "typo", "digitação", "comentário", "renomear", "formatar", "formatação",
    "ajuste simples", "corrigir texto", "atualizar readme", "bump",
]

# Arquivos citados na instrução, em duas formas: com caminho
# (`src/billing/charge.py`) ou nome solto com extensão conhecida de código
# (`models.py`). A segunda alternativa é restrita a extensões reais para não
# contar "versão 1.2" como arquivo.
_CODE_EXTENSIONS = (
    "py|ts|tsx|js|jsx|css|scss|html|md|json|ya?ml|toml|go|rs|java|kt|rb|php|sql|sh"
)
_FILE_PATH_RE = re.compile(
    rf"(?:[\w.-]+/)+[\w-]+\.\w{{1,6}}\b|\b[\w-]+\.(?:{_CODE_EXTENSIONS})\b"
)

# Um pedido detalhado o bastante para passar disto costuma trazer restrições
# e casos de borda junto — sozinho não decide nada, só soma com os demais.
LONG_INSTRUCTION_CHARS = 300
MANY_FILES = 3


def instruction_complexity(instruction: str) -> int:
    """Estima o peso de uma instrução: SIMPLE, MEDIUM ou COMPLEX (RF-18).

    Combina os sinais que o próprio PRD sugere — decisão arquitetural
    explícita e quantidade de arquivos citados — com o tamanho do pedido.
    """
    text = (instruction or "").lower()
    if not text.strip():
        return MEDIUM

    files_mentioned = len(set(_FILE_PATH_RE.findall(text)))
    has_complex_term = any(term in text for term in _COMPLEX_TERMS)
    has_simple_term = any(term in text for term in _SIMPLE_TERMS)

    score = 0
    if has_complex_term:
        score += 2
    if files_mentioned >= MANY_FILES:
        score += 1
    if len(text) >= LONG_INSTRUCTION_CHARS:
        score += 1
    if has_simple_term:
        score -= 2

    if score >= 2:
        return COMPLEX
    if score <= -1:
        return SIMPLE
    return MEDIUM


# Ajuste do roteamento automático conforme a complexidade estimada. Só
# Plan/Execute mudam — Discuss e Verify são leitura/checagem em qualquer
# tamanho de tarefa.
_COMPLEXITY_ROUTING = {
    (Phase.PLAN, COMPLEX): Project.Model.OPUS,
    (Phase.EXECUTE, COMPLEX): Project.Model.OPUS,
    (Phase.PLAN, SIMPLE): Project.Model.HAIKU,
    (Phase.EXECUTE, SIMPLE): Project.Model.HAIKU,
}


def choose_model(
    project: Project,
    phase: str,
    consecutive_verify_failures: int,
    model_override: str = "",
    instruction: str = "",
) -> str:
    """Decide o modelo para uma fase de um TaskRun (RF-18/19).

    Precedência: override da tarefa > modelo padrão do projeto > roteamento
    automático por fase e complexidade da instrução. Os dois primeiros são
    escolhas explícitas de um humano e não participam do escalonamento — se
    alguém fixou um modelo, não gastamos Opus às escondidas por trás dessa
    decisão.
    """
    if model_override and model_override != Project.Model.AUTO:
        return model_override
    if project.default_model != Project.Model.AUTO:
        return project.default_model

    # Escalonamento por falha vence a estimativa: a instrução pode parecer
    # simples e o trabalho ter se mostrado difícil na prática.
    if phase in _ESCALATABLE_PHASES and consecutive_verify_failures >= ESCALATION_THRESHOLD:
        return Project.Model.OPUS

    complexity = instruction_complexity(instruction)
    return _COMPLEXITY_ROUTING.get((phase, complexity), _AUTO_ROUTING[phase])
