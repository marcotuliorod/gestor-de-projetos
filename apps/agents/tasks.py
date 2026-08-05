import logging

from celery import shared_task
from django.utils import timezone

from apps.status.github_client import get_installation_client
from apps.status.models import ProjectState, StatusSnapshot
from apps.status.tasks import collect_status

from . import agent_client, workspace
from .model_routing import choose_model
from .models import TaskRun, TaskRunStep

logger = logging.getLogger(__name__)

# "Ship" fica fora deste loop — só roda no endpoint /approve/, depois de
# revisão humana (RNF-01/RF-10: nunca push/PR sem aprovação).
PHASE_ORDER = [
    TaskRunStep.Phase.DISCUSS,
    TaskRunStep.Phase.PLAN,
    TaskRunStep.Phase.EXECUTE,
    TaskRunStep.Phase.VERIFY,
]


@shared_task(bind=True, max_retries=0)
def run_task_run(self, task_run_id):
    """Orquestra as fases Discuss→Plan→Execute→Verify de um TaskRun
    (RF-07..10, RF-17). Nunca deixa a exceção subir: qualquer falha grava
    um TaskRunStep FAILED + TaskRun.state=FAILED com um summary útil, para
    a tela de Run sempre poder oferecer "Tentar de novo"/"Editar instrução".
    """
    try:
        task_run = TaskRun.objects.select_related("project").get(pk=task_run_id)
    except TaskRun.DoesNotExist:
        logger.warning("run_task_run: TaskRun %s não existe", task_run_id)
        return None

    project = task_run.project
    task_run.state = TaskRun.State.RUNNING
    task_run.save(update_fields=["state", "updated_at"])
    _flip_board_to_rodando(project)

    try:
        gh = get_installation_client()
        base_branch = gh.get_repo(f"{project.repo_owner}/{project.repo_name}").default_branch
        task_run.base_branch = base_branch
        task_run.branch_name = f"agent/task-{task_run.id}"
        task_run.save(update_fields=["base_branch", "branch_name", "updated_at"])
        worktree_path = workspace.create_worktree(task_run, base_branch)
    except Exception:
        logger.exception("run_task_run: falha ao preparar worktree para TaskRun %s", task_run_id)
        _fail(task_run, "Não consegui preparar o repositório local (clone/branch). Ver logs do worker.")
        collect_status.delay(project.id)
        return None

    context = {"instruction": task_run.instruction, "adjustment": task_run.adjustment_instructions}
    for phase in PHASE_ORDER:
        ok = _run_phase(task_run, phase, worktree_path, context)
        if not ok:
            _fail(task_run, context.get("last_error", f"Falha na fase {phase}."))
            collect_status.delay(project.id)
            return None

    task_run.summary = context.get("summary", "Alterações prontas para revisão.")[:280]
    task_run.state = TaskRun.State.NEEDS_REVIEW
    task_run.save(update_fields=["summary", "state", "updated_at"])
    collect_status.delay(project.id)
    return task_run.id


def _run_phase(task_run, phase, worktree_path, context) -> bool:
    attempt = TaskRunStep.objects.filter(task_run=task_run, phase=phase).count() + 1
    model = choose_model(task_run.project, phase, task_run.consecutive_verify_failures)
    step = TaskRunStep.objects.create(
        task_run=task_run,
        phase=phase,
        attempt=attempt,
        status=TaskRunStep.Status.RUNNING,
        model_used=model,
        started_at=timezone.now(),
    )
    _publish(task_run.id, step.id)

    try:
        result = agent_client.run_phase(
            phase=phase,
            model=model,
            project=task_run.project,
            instruction=f"{task_run.instruction}\n{task_run.adjustment_instructions}".strip(),
            worktree_path=worktree_path,
            context=context,
        )
    except Exception as exc:
        logger.exception("run_task_run: fase %s falhou para TaskRun %s", phase, task_run.id)
        step.status = TaskRunStep.Status.FAILED
        step.detail = f"Erro inesperado: {exc}"[:4000]
        step.finished_at = timezone.now()
        step.save(update_fields=["status", "detail", "finished_at"])
        _publish(task_run.id, step.id)
        context["last_error"] = step.detail
        _update_verify_counter(task_run, phase, ok=False)
        return False

    step.status = TaskRunStep.Status.DONE if result.ok else TaskRunStep.Status.FAILED
    step.detail = result.detail[:4000]
    step.cost_usd = result.cost_usd
    step.finished_at = timezone.now()
    step.save(update_fields=["status", "detail", "cost_usd", "finished_at"])
    _publish(task_run.id, step.id)
    context.update(result.context_updates)

    _update_verify_counter(task_run, phase, ok=result.ok)
    if not result.ok:
        context["last_error"] = result.detail
    return result.ok


def _update_verify_counter(task_run, phase, ok: bool) -> None:
    if phase != TaskRunStep.Phase.VERIFY:
        return
    task_run.consecutive_verify_failures = 0 if ok else task_run.consecutive_verify_failures + 1
    task_run.save(update_fields=["consecutive_verify_failures", "updated_at"])


def _fail(task_run, message: str) -> None:
    task_run.state = TaskRun.State.FAILED
    task_run.summary = message[:280]
    task_run.save(update_fields=["state", "summary", "updated_at"])


def _flip_board_to_rodando(project) -> None:
    """Grava um StatusSnapshot(state=RODANDO) diretamente — exceção já
    documentada em apps/status/classify.py: RODANDO nunca vem do
    classificador passivo, só da execução de agentes."""
    StatusSnapshot.objects.create(
        project=project,
        state=ProjectState.RODANDO,
        summary="Agente rodando uma tarefa neste projeto.",
    )


def _publish(task_run_id, step_id) -> None:
    """Publica no canal Redis pub/sub para o SSE. Best-effort: se Redis
    falhar, a UI ainda funciona via polling/GET normal (ver views.py)."""
    from django.conf import settings

    try:
        import redis

        r = redis.from_url(settings.REDIS_URL)
        r.publish(f"task_run:{task_run_id}", str(step_id))
    except Exception:
        logger.warning("run_task_run: falha ao publicar evento SSE (não-fatal)", exc_info=True)


@shared_task
def dispatch_nightly_queue():
    """Enfileira todos os TaskRuns QUEUED+NIGHTLY (agendado via celery-beat
    às 02:00 — ver management command bootstrap_agents_beat_schedule).

    Pausa por inteiro (RF-12) se o orçamento semanal estourou o limiar —
    tarefas urgency=now nunca são afetadas por isso, só a fila noturna.
    """
    from apps.budget.tracking import budget_state

    if budget_state()["should_pause_nightly"]:
        logger.info("dispatch_nightly_queue: pausado — orçamento semanal no limiar")
        return

    runs = TaskRun.objects.filter(state=TaskRun.State.QUEUED, urgency=TaskRun.Urgency.NIGHTLY)
    for task_run_id in runs.values_list("id", flat=True):
        run_task_run.delay(task_run_id)
