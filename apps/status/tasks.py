import logging

from celery import shared_task

from apps.projects.models import Project

from .models import ProjectState, StatusSnapshot

logger = logging.getLogger(__name__)


@shared_task
def collect_status(project_id):
    """Coleta o estado real de um projeto e grava um StatusSnapshot.

    STUB (Fase 1): por ora apenas cria um snapshot vazio e loga. A leitura
    real via GitHub App + webhooks + `git fetch` (PyGithub) entra em fase
    posterior — este é o ponto de extensão RF-04.
    """
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        logger.warning("collect_status: projeto %s não existe", project_id)
        return None

    # TODO(github): substituir por leitura real (branch, ahead/behind, PRs,
    # CI, último commit, arquivos modificados) e classificação de estado.
    snapshot = StatusSnapshot.objects.create(
        project=project,
        state=ProjectState.PARADO,
        summary="Snapshot stub — coletor real ainda não implementado.",
    )
    logger.info("collect_status: snapshot %s criado para %s", snapshot.pk, project)
    return snapshot.pk


@shared_task
def collect_all_status():
    """Enfileira coleta para todos os projetos (agendado via celery-beat)."""
    for pid in Project.objects.values_list("id", flat=True):
        collect_status.delay(pid)
