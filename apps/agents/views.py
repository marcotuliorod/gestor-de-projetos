import logging

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.status.github_client import get_installation_client

from . import workspace
from .models import TaskRun
from .serializers import TaskRunSerializer
from .tasks import run_task_run

logger = logging.getLogger(__name__)


class TaskRunViewSet(viewsets.ModelViewSet):
    """CRUD + ciclo de vida de TaskRuns (RF-07..10).

    Sem PUT/PATCH/DELETE — o estado só muda através das actions abaixo,
    cada uma correspondendo a um botão da tela de Run/Diff.
    """

    queryset = TaskRun.objects.select_related("project").prefetch_related("steps")
    serializer_class = TaskRunSerializer
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        task_run = serializer.save()
        if task_run.urgency == TaskRun.Urgency.NOW:
            run_task_run.delay(task_run.id)
        # NIGHTLY: fica QUEUED, pego pelo dispatcher noturno (celery-beat).

    @action(detail=True, methods=["get"])
    def diff(self, request, pk=None):
        task_run = self.get_object()
        if task_run.state not in (TaskRun.State.NEEDS_REVIEW, TaskRun.State.RUNNING):
            return Response({"detail": "Sem diff disponível neste estado."}, status=409)
        try:
            files = workspace.diff_stat(task_run)
        except Exception:
            logger.exception("diff: falha ao calcular diff para TaskRun %s", pk)
            return Response({"detail": "Falha ao calcular o diff — ver logs do worker."}, status=502)
        return Response({"files": files})

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Único lugar do sistema que empurra o branch e abre o PR
        (RNF-01/RF-10) — só a partir de NEEDS_REVIEW."""
        task_run = self.get_object()
        if task_run.state != TaskRun.State.NEEDS_REVIEW:
            return Response({"detail": "TaskRun não está pronto para aprovação."}, status=409)
        try:
            workspace.push_branch(task_run)
            gh = get_installation_client()
            repo = gh.get_repo(f"{task_run.project.repo_owner}/{task_run.project.repo_name}")
            pr = repo.create_pull(
                title=task_run.instruction[:70],
                body=task_run.summary or task_run.instruction,
                head=task_run.branch_name,
                base=task_run.base_branch,
            )
        except Exception:
            logger.exception("approve: falha ao empurrar/abrir PR para TaskRun %s", pk)
            return Response({"detail": "Falha ao abrir PR — ver logs do worker."}, status=502)
        task_run.pr_url = pr.html_url
        task_run.state = TaskRun.State.DONE
        task_run.save(update_fields=["pr_url", "state", "updated_at"])
        return Response(TaskRunSerializer(task_run).data)

    @action(detail=True, methods=["post"], url_path="request-changes")
    def request_changes(self, request, pk=None):
        task_run = self.get_object()
        if task_run.state != TaskRun.State.NEEDS_REVIEW:
            return Response({"detail": "TaskRun não está em revisão."}, status=409)
        adjustment = str(request.data.get("instruction", "")).strip()
        task_run.adjustment_instructions = f"{task_run.adjustment_instructions}\n{adjustment}".strip()
        task_run.state = TaskRun.State.RUNNING
        task_run.save(update_fields=["adjustment_instructions", "state", "updated_at"])
        run_task_run.delay(task_run.id)
        return Response(TaskRunSerializer(task_run).data)

    @action(detail=True, methods=["post"])
    def discard(self, request, pk=None):
        task_run = self.get_object()
        try:
            workspace.discard_worktree(task_run)
        except Exception:
            logger.warning("discard: falha ao remover worktree para TaskRun %s", pk, exc_info=True)
        task_run.state = TaskRun.State.DISCARDED
        task_run.save(update_fields=["state", "updated_at"])
        return Response(TaskRunSerializer(task_run).data)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        task_run = self.get_object()
        if task_run.state != TaskRun.State.FAILED:
            return Response({"detail": "TaskRun não está em estado de falha."}, status=409)
        task_run.consecutive_verify_failures = 0
        task_run.state = TaskRun.State.RUNNING
        task_run.save(update_fields=["consecutive_verify_failures", "state", "updated_at"])
        run_task_run.delay(task_run.id)
        return Response(TaskRunSerializer(task_run).data)

    @action(detail=True, methods=["get"])
    def stream(self, request, pk=None):
        """SSE best-effort via Redis pub/sub: cada mensagem é só um aviso
        para recarregar (GET normal) — os registros no banco são a fonte
        de verdade, sem reconexão/backfill nesta versão."""

        def event_stream():
            import redis

            r = redis.from_url(settings.REDIS_URL)
            pubsub = r.pubsub()
            pubsub.subscribe(f"task_run:{pk}")
            for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data'].decode()}\n\n"

        return StreamingHttpResponse(event_stream(), content_type="text/event-stream")
