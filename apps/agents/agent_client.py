"""Interface estável para chamar o agente de codificação por fase.

`run_phase()` é o único ponto de contato com o Claude Agent SDK — mantém
`tasks.py` e seus testes independentes de qual pacote/assinatura real do
SDK acabar sendo usado.

IMPORTANTE: o nome exato do pacote pip e a assinatura de `query()` (ou
equivalente) do Claude Agent SDK Python NÃO estão confirmados nesta
implementação — ver nota no plano. Até um spike confirmar isso contra a
documentação oficial atual, `AGENTS_FAKE_MODE=True` (padrão em dev/test)
mantém todo o resto do sistema (orquestração, worktree, SSE, diff)
testável sem gastar crédito de API nem depender do spike.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class PhaseResult:
    ok: bool
    detail: str
    context_updates: dict = field(default_factory=dict)


def run_phase(
    *,
    phase: str,
    model: str,
    project,
    instruction: str,
    worktree_path: Path,
    context: dict,
) -> PhaseResult:
    if getattr(settings, "AGENTS_FAKE_MODE", True):
        return _run_phase_fake(phase, model, project, instruction, worktree_path, context)
    return _run_phase_real(phase, model, project, instruction, worktree_path, context)


def _run_phase_fake(phase, model, project, instruction, worktree_path, context) -> PhaseResult:
    """Modo determinístico para dev/test: não chama nenhuma API externa.

    Discuss/Plan/Verify/Ship só retornam um resumo canned. Execute escreve
    uma mudança trivial e real no worktree, para que exista um diff de
    verdade para exercitar diff_stat()/a tela de Diff.
    """
    from .models import TaskRunStep

    if phase == TaskRunStep.Phase.EXECUTE:
        note_path = Path(worktree_path) / "AGENT_NOTES.md"
        existing = note_path.read_text() if note_path.exists() else "# Notas do agente\n\n"
        note_path.write_text(existing + f"- [fake/{model}] {instruction.strip()}\n")
        return PhaseResult(
            ok=True,
            detail=f"[fake] Escrevi uma anotação em AGENT_NOTES.md descrevendo a instrução (modelo: {model}).",
            context_updates={"execute_summary": "Anotação adicionada em AGENT_NOTES.md."},
        )

    detail_by_phase = {
        TaskRunStep.Phase.DISCUSS: "[fake] Instrução entendida, nada a esclarecer.",
        TaskRunStep.Phase.PLAN: "[fake] Plano: um único passo de Execute cobre a instrução.",
        TaskRunStep.Phase.VERIFY: "[fake] Verificação (fake) passou — nenhum teste real rodado.",
        TaskRunStep.Phase.SHIP: "[fake] Pronto para revisão humana.",
    }
    return PhaseResult(
        ok=True,
        detail=detail_by_phase.get(phase, "[fake] ok"),
        context_updates={"summary": "Alterações de teste (modo fake) prontas para revisão."},
    )


def _run_phase_real(phase, model, project, instruction, worktree_path, context) -> PhaseResult:
    raise NotImplementedError(
        "Integração real com o Claude Agent SDK ainda não implementada — "
        "requer um spike para confirmar o pacote/assinatura corretos "
        "(ver seção 4 do plano de execução de agentes) antes de escrever "
        "esta função. Use AGENTS_FAKE_MODE=True até lá."
    )
