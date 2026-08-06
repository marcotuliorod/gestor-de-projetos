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
