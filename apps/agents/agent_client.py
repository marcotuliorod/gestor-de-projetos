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
    # Custo real da chamada (USD) — None em modo fake. Alimenta o Token
    # Budget Scheduler (apps.budget) via TaskRunStep.cost_usd.
    cost_usd: float | None = None
    # Tokens de prompt lidos/gravados no cache (RF-22). Zero significa que o
    # cache não pegou — é assim que se descobre que a opção foi ignorada.
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


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
            cost_usd=None,
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
        cost_usd=None,
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
        # Os comandos do projeto não são repetidos aqui: vivem no contexto
        # estável do system prompt (RF-22), que é o que o cache reaproveita.
        return (
            "Você está na fase Verify. Rode os comandos de teste/lint do "
            "projeto (listados no contexto do projeto) se existirem, e "
            "confirme se as alterações da fase Execute estão corretas. Se algo "
            "falhar, corrija e rode de novo. Resuma o resultado (passou ou "
            "falhou, e por quê) em até 3 linhas.\n\n"
            f"O que foi feito na fase Execute:\n{context.get('execute_summary', '(nenhum)')}"
        )
    # SHIP não é chamado por este loop (roda só após aprovação humana), mas
    # fica aqui por completude da interface.
    return f"Resuma em até 2 linhas o resultado final da tarefa: {instruction}"


def stable_project_context(project) -> str:
    """Contexto do projeto que não muda entre fases nem entre execuções
    (RF-22).

    Vai no `append` do system prompt, e não nas mensagens por fase, porque é
    o prefixo estável que o cache de prompt consegue reaproveitar. Não pode
    conter nada volátil (id da tarefa, timestamp, resumo da fase anterior) —
    qualquer variação aqui invalida o cache de todas as execuções seguintes.

    Deliberadamente **não** escrevemos um CLAUDE.md no worktree para isso:
    `commit_worktree_changes` faz `git add -A`, então o arquivo entraria no
    diff de toda tarefa e poluiria os PRs. Um CLAUDE.md que o repositório já
    tenha continua sendo carregado pelo próprio CLI.
    """
    linhas = [f"Projeto: {project.name}"]
    if project.stack:
        linhas.append(f"Stack: {project.stack}")
    for rotulo, comando in (
        ("Build", project.build_command),
        ("Testes", project.test_command),
        ("Lint", project.lint_command),
    ):
        if comando:
            linhas.append(f"{rotulo}: {comando}")

    linhas.append(
        "Regras invariantes: trabalhe apenas dentro deste worktree; nunca "
        "faça commit na branch padrão nem push — a revisão e a abertura do PR "
        "são feitas por um humano fora desta sessão."
    )
    return "\n".join(linhas)


def _cache_tokens(usage) -> tuple[int, int]:
    """Tokens lidos e escritos no cache de prompt, de `ResultMessage.usage`.

    Nomes seguem o padrão da API (`cache_read_input_tokens`); tolera ausência
    porque a opção de cache pode ser ignorada em silêncio por CLI antigo — e
    nesse caso o número vira zero, que é justamente o sinal de que não pegou.
    """
    if not isinstance(usage, dict):
        return 0, 0
    leitura = usage.get("cache_read_input_tokens") or 0
    escrita = usage.get("cache_creation_input_tokens") or 0
    try:
        return int(leitura), int(escrita)
    except (TypeError, ValueError):
        return 0, 0


def disallowed_tools_for(project) -> list[str]:
    """Traduz `Project.agent_permissions` em ferramentas bloqueadas (RF-03).

    Os defaults preservam o comportamento anterior ao campo existir (tudo
    liberado) — projetos já cadastrados têm `agent_permissions` vazio e não
    podem mudar de comportamento em silêncio só porque a tela de edição
    passou a existir.
    """
    permissions = project.agent_permissions or {}
    blocked = []
    if not permissions.get("allow_bash", True):
        blocked.append("Bash")
    if not permissions.get("allow_web", True):
        blocked.extend(["WebFetch", "WebSearch"])
    return blocked


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
        disallowed_tools=disallowed_tools_for(project),
        # RF-22: estende o prompt do Claude Code em vez de substituí-lo
        # (substituir custaria as instruções de ferramenta) e mantém o
        # prefixo estável entre fases para o cache de prompt pegar.
        # `exclude_dynamic_sections` tira diretório/git status do prefixo;
        # CLIs antigos ignoram a opção em silêncio, por isso medimos o
        # resultado em vez de presumir (ver cache_read_tokens).
        #
        # Medido contra a API real com o CLI 2.1.222: a 1ª fase gravou 25.354
        # tokens no cache e a 2ª leu 22.810 deles, com o custo caindo de
        # $0.0328 para $0.0065. Se esse número voltar a zero em produção, é
        # sinal de que a opção parou de valer.
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": stable_project_context(project),
            "exclude_dynamic_sections": True,
        },
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
    cache_read, cache_write = _cache_tokens(result.usage)
    logger.info(
        "agent_client: fase %s — cache lido=%s gravado=%s custo=%s",
        phase,
        cache_read,
        cache_write,
        result.total_cost_usd,
    )
    return PhaseResult(
        ok=ok,
        detail=detail[:4000],
        context_updates={f"{phase}_summary": detail[:280]},
        cost_usd=result.total_cost_usd,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )


async def _collect_result(prompt: str, options):
    from claude_agent_sdk import ResultMessage, query

    result_message = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result_message = message
    return result_message
