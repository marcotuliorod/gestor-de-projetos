from unittest.mock import MagicMock, patch

from rest_framework.test import APIClient, APITestCase

from apps.agents.models import TaskRun
from apps.projects.models import Project


class TaskRunViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="teste", repo_url="https://github.com/ju/teste")
        self.project.repo_owner, self.project.repo_name = "ju", "teste"
        self.project.save()

    @patch("apps.agents.views.run_task_run.delay")
    def test_create_dispatches_when_now(self, mock_delay):
        response = self.client.post(
            "/api/task-runs/",
            {"project": self.project.id, "instruction": "faz algo", "urgency": "now"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        task_run_id = response.data["id"]
        mock_delay.assert_called_once_with(task_run_id)

    @patch("apps.agents.views.run_task_run.delay")
    def test_create_does_not_dispatch_when_nightly(self, mock_delay):
        response = self.client.post(
            "/api/task-runs/",
            {"project": self.project.id, "instruction": "faz algo", "urgency": "nightly"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        mock_delay.assert_not_called()

    def test_diff_rejected_outside_reviewable_state(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="x", state=TaskRun.State.QUEUED)
        response = self.client.get(f"/api/task-runs/{task_run.id}/diff/")
        self.assertEqual(response.status_code, 409)

    @patch("apps.agents.views.workspace.diff_stat", return_value=[{"path": "a.py", "added": 1, "removed": 0, "lines": []}])
    def test_diff_returns_files_when_needs_review(self, mock_diff):
        task_run = TaskRun.objects.create(
            project=self.project, instruction="x", state=TaskRun.State.NEEDS_REVIEW
        )
        response = self.client.get(f"/api/task-runs/{task_run.id}/diff/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["files"][0]["path"], "a.py")

    def test_approve_rejected_outside_needs_review(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="x", state=TaskRun.State.RUNNING)
        response = self.client.post(f"/api/task-runs/{task_run.id}/approve/")
        self.assertEqual(response.status_code, 409)

    @patch("apps.agents.views.send_telegram_message")
    @patch("apps.agents.views.get_installation_client")
    @patch("apps.agents.views.workspace.push_branch")
    def test_approve_pushes_and_opens_pr(self, mock_push, mock_gh_client, mock_notify):
        pr = MagicMock()
        pr.html_url = "https://github.com/ju/teste/pull/1"
        mock_gh_client.return_value.get_repo.return_value.create_pull.return_value = pr

        task_run = TaskRun.objects.create(
            project=self.project,
            instruction="x",
            state=TaskRun.State.NEEDS_REVIEW,
            branch_name="agent/task-1",
            base_branch="main",
        )
        response = self.client.post(f"/api/task-runs/{task_run.id}/approve/")

        self.assertEqual(response.status_code, 200)
        mock_push.assert_called_once_with(task_run)
        task_run.refresh_from_db()
        self.assertEqual(task_run.state, TaskRun.State.DONE)
        self.assertEqual(task_run.pr_url, pr.html_url)
        mock_notify.assert_called_once()
        self.assertIn(pr.html_url, mock_notify.call_args[0][0])

    @patch("apps.agents.views.run_task_run.delay")
    def test_request_changes_requeues(self, mock_delay):
        task_run = TaskRun.objects.create(
            project=self.project, instruction="x", state=TaskRun.State.NEEDS_REVIEW
        )
        response = self.client.post(
            f"/api/task-runs/{task_run.id}/request-changes/",
            {"instruction": "ajusta isso"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        task_run.refresh_from_db()
        self.assertEqual(task_run.state, TaskRun.State.RUNNING)
        self.assertIn("ajusta isso", task_run.adjustment_instructions)
        mock_delay.assert_called_once_with(task_run.id)

    @patch("apps.agents.views.workspace.discard_worktree")
    def test_discard_transitions_to_discarded(self, mock_discard):
        task_run = TaskRun.objects.create(
            project=self.project, instruction="x", state=TaskRun.State.NEEDS_REVIEW
        )
        response = self.client.post(f"/api/task-runs/{task_run.id}/discard/")
        self.assertEqual(response.status_code, 200)
        task_run.refresh_from_db()
        self.assertEqual(task_run.state, TaskRun.State.DISCARDED)

    @patch("apps.agents.views.run_task_run.delay")
    def test_retry_only_from_failed(self, mock_delay):
        task_run = TaskRun.objects.create(
            project=self.project,
            instruction="x",
            state=TaskRun.State.FAILED,
            consecutive_verify_failures=2,
        )
        response = self.client.post(f"/api/task-runs/{task_run.id}/retry/")
        self.assertEqual(response.status_code, 200)
        task_run.refresh_from_db()
        self.assertEqual(task_run.state, TaskRun.State.RUNNING)
        self.assertEqual(task_run.consecutive_verify_failures, 0)
        mock_delay.assert_called_once_with(task_run.id)

    def test_retry_rejected_outside_failed(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="x", state=TaskRun.State.DONE)
        response = self.client.post(f"/api/task-runs/{task_run.id}/retry/")
        self.assertEqual(response.status_code, 409)


class PrTitleTests(APITestCase):
    """Regressão vista num PR real: o título saía dos primeiros 70
    caracteres da instrução, o que cortava no meio da frase quando a
    instrução era longa (caso do scaffold de projeto novo)."""

    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="teste", repo_url="https://github.com/ju/teste")

    @patch("apps.agents.views.send_telegram_message")
    @patch("apps.agents.views.get_installation_client")
    @patch("apps.agents.views.workspace.push_branch")
    def test_pr_title_is_the_first_line(self, mock_push, mock_gh, mock_notify):
        pr = MagicMock()
        pr.html_url = "https://github.com/ju/teste/pull/1"
        mock_gh.return_value.get_repo.return_value.create_pull.return_value = pr

        task_run = TaskRun.objects.create(
            project=self.project,
            instruction="Scaffold inicial do projeto loja\n\nEste repositório está vazio.\nMonte a estrutura.",
            state=TaskRun.State.NEEDS_REVIEW,
            branch_name="agent/task-1",
            base_branch="main",
        )
        self.client.post(f"/api/task-runs/{task_run.id}/approve/")

        title = mock_gh.return_value.get_repo.return_value.create_pull.call_args.kwargs["title"]
        self.assertEqual(title, "Scaffold inicial do projeto loja")

    @patch("apps.agents.views.send_telegram_message")
    @patch("apps.agents.views.get_installation_client")
    @patch("apps.agents.views.workspace.push_branch")
    def test_long_single_line_is_still_truncated(self, mock_push, mock_gh, mock_notify):
        pr = MagicMock()
        pr.html_url = "https://github.com/ju/teste/pull/1"
        mock_gh.return_value.get_repo.return_value.create_pull.return_value = pr

        task_run = TaskRun.objects.create(
            project=self.project,
            instruction="x" * 200,
            state=TaskRun.State.NEEDS_REVIEW,
            branch_name="agent/task-2",
            base_branch="main",
        )
        self.client.post(f"/api/task-runs/{task_run.id}/approve/")

        title = mock_gh.return_value.get_repo.return_value.create_pull.call_args.kwargs["title"]
        self.assertEqual(len(title), 70)


class StepPayloadTests(APITestCase):
    """RF-08: a tela de Run mostra duração e custo por fase — o custo
    precisa sair no payload, o que não acontecia."""

    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="teste")

    def test_cost_is_exposed(self):
        from decimal import Decimal

        from apps.agents.models import TaskRunStep

        task_run = TaskRun.objects.create(project=self.project, instruction="x")
        TaskRunStep.objects.create(
            task_run=task_run,
            phase=TaskRunStep.Phase.EXECUTE,
            status=TaskRunStep.Status.DONE,
            model_used="sonnet",
            cost_usd=Decimal("0.1234"),
        )

        response = self.client.get(f"/api/task-runs/{task_run.id}/")

        step = response.data["steps"][0]
        self.assertEqual(str(step["cost_usd"]), "0.1234")
        self.assertEqual(step["model_used"], "sonnet")

    def test_cost_is_null_in_fake_mode(self):
        from apps.agents.models import TaskRunStep

        task_run = TaskRun.objects.create(project=self.project, instruction="x")
        TaskRunStep.objects.create(task_run=task_run, phase=TaskRunStep.Phase.DISCUSS)

        response = self.client.get(f"/api/task-runs/{task_run.id}/")

        self.assertIsNone(response.data["steps"][0]["cost_usd"])


class ModelOverrideApiTests(APITestCase):
    """RF-19: o Composer envia o modelo escolhido na criação da tarefa."""

    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="teste")

    @patch("apps.agents.views.run_task_run.delay")
    def test_override_is_accepted_and_returned(self, mock_delay):
        response = self.client.post(
            "/api/task-runs/",
            {"project": self.project.id, "instruction": "x", "urgency": "now", "model_override": "opus"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["model_override"], "opus")
        self.assertEqual(TaskRun.objects.get(pk=response.data["id"]).model_override, "opus")

    @patch("apps.agents.views.run_task_run.delay")
    def test_omitting_override_means_automatic(self, mock_delay):
        response = self.client.post(
            "/api/task-runs/",
            {"project": self.project.id, "instruction": "x", "urgency": "now"},
            format="json",
        )
        self.assertEqual(response.data["model_override"], "")


class StreamContentNegotiationTests(APITestCase):
    """Regressão achada navegando o app de verdade: o `EventSource` nativo
    do navegador manda `Accept: text/event-stream`, e nenhum renderer padrão
    do DRF declara esse media type — a negociação de conteúdo rejeitava a
    requisição com 406 antes do método `stream()` sequer rodar. O SSE só
    parecia funcionar porque o polling de fallback (Run.tsx) cobria o
    buraco silenciosamente."""

    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="teste")

    def test_event_source_accept_header_is_not_rejected(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="x")

        response = self.client.get(
            f"/api/task-runs/{task_run.id}/stream/", HTTP_ACCEPT="text/event-stream"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")


class StreamTerminationTests(APITestCase):
    """Regressão real, achada navegando o app: `pubsub.listen()` bloqueia
    para sempre — sem nenhuma mensagem publicada, a thread do generator
    nunca retorna. Uma única aba com a tela de Run aberta travou o processo
    do Uvicorn inteiro no reload seguinte, porque ele esperava essa "tarefa
    de fundo" terminar. O generator agora consulta o estado do TaskRun e se
    encerra sozinho assim que ele chega a um estado terminal."""

    def setUp(self):
        self.client = APIClient()
        self.project = Project.objects.create(name="teste")

    def test_stream_ends_immediately_for_a_finished_task_run(self):
        task_run = TaskRun.objects.create(
            project=self.project, instruction="x", state=TaskRun.State.NEEDS_REVIEW
        )

        response = self.client.get(
            f"/api/task-runs/{task_run.id}/stream/", HTTP_ACCEPT="text/event-stream"
        )

        # Consumir o generator não deve travar — se travar, o teste key
        # não retorna e o runner acaba por timeout.
        chunks = list(response.streaming_content)
        self.assertEqual(chunks, [])

    def test_stream_ends_for_failed_and_discarded_states_too(self):
        for state in (TaskRun.State.FAILED, TaskRun.State.DONE, TaskRun.State.DISCARDED):
            task_run = TaskRun.objects.create(project=self.project, instruction="x", state=state)
            response = self.client.get(
                f"/api/task-runs/{task_run.id}/stream/", HTTP_ACCEPT="text/event-stream"
            )
            self.assertEqual(list(response.streaming_content), [], f"não encerrou para state={state}")
