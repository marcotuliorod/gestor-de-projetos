"""Interface estável para chamar o agente de codificação por fase.

`run_phase()` é o único ponto de contato com o Claude Agent SDK — mantém
`tasks.py` e seus testes independentes dos detalhes do SDK.

Pacote confirmado direto do PyPI/código-fonte (não de resumo de terceiros):
`claude-agent-sdk` (import `claude_agent_sdk`), função `query()` assíncrona.
Cada fase é uma chamada `query()` isolada e sem sessão compartilhada — isso
por si só já dá o "contexto limpo por fase" que RF-17 pede, sem precisar de
nenhuma opção especial do SDK para isso.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# IDs de modelo reais — não são aliases adivinhados, vêm da lista de modelos
# atuais conhecida neste ambiente.
MODEL_IDS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
}

# Cap de segurança: nenhuma fase deve rodar indefinidamente sem humano
# supervisionando.
MAX_TURNS_PER_PHASE = 20


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


def _build_prompt(phase: str, project, instruction: str, context: dict) -> str:
    from .models import TaskRunStep

    if phase == TaskRunStep.Phase.DISCUSS:
        return (
            "Você está na fase Discuss de uma tarefa de desenvolvimento. Leia o "
            "repositório o suficiente para entender o que a instrução abaixo "
            "pede. Não faça nenhuma alteração de código nesta fase — apenas "
            "responda com um resumo de até 3 frases confirmando o que fará e "
            "citando dúvidas/suposições relevantes.\n\n"
            f"Instrução do usuário:\n{instruction}"
        )
    if phase == TaskRunStep.Phase.PLAN:
        return (
            "Você está na fase Plan. Com base na instrução e no entendimento da "
            "fase Discuss abaixo, produza um plano curto (lista de passos) do "
            "que será alterado. Não edite arquivos ainda.\n\n"
            f"Instrução:\n{instruction}\n\n"
            f"Resumo da fase Discuss:\n{context.get('discuss_summary', '(nenhum)')}"
        )
    if phase == TaskRunStep.Phase.EXECUTE:
        return (
            "Você está na fase Execute. Implemente o plano abaixo, editando os "
            "arquivos necessários no repositório. Ao final, resuma em até 3 "
            "linhas o que foi alterado.\n\n"
            f"Instrução:\n{instruction}\n\n"
            f"Plano:\n{context.get('plan_summary', '(nenhum)')}"
        )
    if phase == TaskRunStep.Phase.VERIFY:
        commands = "\n".join(
            f"- {label}: {cmd}"
            for label, cmd in [
                ("build", project.build_command),
                ("test", project.test_command),
                ("lint", project.lint_command),
            ]
            if cmd
        )
        return (
            "Você está na fase Verify. Rode os comandos de teste/lint do "
            "projeto se existirem, e confirme se as alterações da fase Execute "
            "estão corretas. Se algo falhar, corrija e rode de novo. Resuma o "
            "resultado (passou ou falhou, e por quê) em até 3 linhas.\n\n"
            f"Comandos disponíveis:\n{commands or '(nenhum configurado)'}\n\n"
            f"O que foi feito na fase Execute:\n{context.get('execute_summary', '(nenhum)')}"
        )
    # SHIP não é chamado por este loop (roda só após aprovação humana), mas
    # fica aqui por completude da interface.
    return f"Resuma em até 2 linhas o resultado final da tarefa: {instruction}"


def _run_phase_real(phase, model, project, instruction, worktree_path, context) -> PhaseResult:
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKError

    prompt = _build_prompt(phase, project, instruction, context)
    options = ClaudeAgentOptions(
        cwd=str(worktree_path),
        model=MODEL_IDS.get(model, model),
        # Sem humano para aprovar ferramentas — precisa rodar sem prompts.
        # Isolamento real vem do worktree dedicado + sandbox abaixo, não de
        # aprovação manual (que não existe neste contexto headless).
        permission_mode="bypassPermissions",
        # Restringe o que comandos Bash do agente conseguem tocar — mitiga o
        # risco de um `cat .env`/acesso fora do worktree. enableWeakerNestedSandbox
        # é a opção documentada para containers Docker sem privilégio extra.
        sandbox={"enabled": True, "enableWeakerNestedSandbox": True},
        max_turns=MAX_TURNS_PER_PHASE,
    )

    try:
        result = asyncio.run(_collect_result(prompt, options))
    except ClaudeSDKError as exc:
        logger.exception("agent_client: erro do Agent SDK na fase %s", phase)
        return PhaseResult(ok=False, detail=f"Erro do Agent SDK: {exc}"[:4000])
    except Exception as exc:
        logger.exception("agent_client: erro inesperado na fase %s", phase)
        return PhaseResult(ok=False, detail=f"Erro inesperado ao chamar o agente: {exc}"[:4000])

    if result is None:
        return PhaseResult(ok=False, detail="O agente não retornou um resultado final (sem ResultMessage).")

    detail = (result.result or "").strip() or "(sem texto de resultado)"
    ok = not result.is_error
    return PhaseResult(
        ok=ok,
        detail=detail[:4000],
        context_updates={f"{phase}_summary": detail[:280]},
    )


async def _collect_result(prompt: str, options):
    from claude_agent_sdk import ResultMessage, query

    result_message = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_message = message
    return result_message
