import logging

import github
from celery import shared_task

from apps.projects.models import Project

from .classify import classify_state
from .github_client import collect_repo_status, get_installation_client
from .models import ProjectState, StatusSnapshot

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def collect_status(self, project_id):
    """Coleta o estado real de um projeto via GitHub App e grava um
    StatusSnapshot (RF-04/05/06). Sem clone local nesta fase — só API REST
    (branch padrão, PRs abertos, CI, e ahead/behind/changed_files quando há
    PR aberto); a leitura via clone/worktree entra junto com a execução de
    agentes.

    Nunca deixa a exceção subir: qualquer falha vira um snapshot degradado
    (state=PARADO, erro no summary) para o Board sempre mostrar algo.
    """
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        logger.warning("collect_status: projeto %s não existe", project_id)
        return None

    if not project.repo_owner or not project.repo_name:
        StatusSnapshot.objects.create(
            project=project,
            state=ProjectState.PARADO,
            summary="repo_url não pôde ser interpretado como owner/repo do GitHub.",
        )
        return None

    try:
        gh = get_installation_client()
        raw = collect_repo_status(gh, project.repo_owner, project.repo_name)
    except github.RateLimitExceededException as exc:
        logger.warning("collect_status: rate limit para %s", project)
        raise self.retry(exc=exc, countdown=300)
    except github.GithubException as exc:
        message = (exc.data or {}).get("message", "") if hasattr(exc, "data") else ""
        StatusSnapshot.objects.create(
            project=project,
            state=ProjectState.PARADO,
            summary=f"Erro ao consultar GitHub: {exc.status} {message}"[:280],
        )
        logger.exception("collect_status: erro GitHub para %s", project)
        return None
    except Exception:
        logger.exception("collect_status: erro inesperado para %s", project)
        StatusSnapshot.objects.create(
            project=project,
            state=ProjectState.PARADO,
            summary="Erro inesperado durante a coleta — ver logs do worker.",
        )
        return None

    state, summary = classify_state(raw)
    snapshot = StatusSnapshot.objects.create(project=project, state=state, summary=summary, **raw)
    logger.info("collect_status: snapshot %s criado para %s", snapshot.pk, project)
    return snapshot.pk


@shared_task
def collect_all_status():
    """Enfileira coleta para todos os projetos (agendado via celery-beat)."""
    for pid in Project.objects.values_list("id", flat=True):
        collect_status.delay(pid)
