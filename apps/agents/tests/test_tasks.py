import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.agents.models import TaskRun, TaskRunStep
from apps.agents.tasks import PHASE_ORDER, run_task_run
from apps.projects.models import Project
from apps.status.models import ProjectState, StatusSnapshot


def _run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _make_remote(base: Path) -> Path:
    remote_path = base / "remote.git"
    _run(["git", "init", "--bare", "-b", "main", str(remote_path)])
    seed = base / "seed"
    seed.mkdir()
    _run(["git", "init", "-b", "main", str(seed)])
    _run(["git", "config", "user.email", "t@example.com"], cwd=seed)
    _run(["git", "config", "user.name", "t"], cwd=seed)
    (seed / "README.md").write_text("hello\n")
    _run(["git", "add", "."], cwd=seed)
    _run(["git", "commit", "-m", "init"], cwd=seed)
    _run(["git", "remote", "add", "origin", str(remote_path)], cwd=seed)
    _run(["git", "push", "origin", "main"], cwd=seed)
    return remote_path


@override_settings(AGENTS_FAKE_MODE=True)
class RunTaskRunTests(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.remote_path = _make_remote(base)

        self.repo_root_override = override_settings(AGENTS_REPO_ROOT=str(base / "repos"))
        self.repo_root_override.enable()
        self.addCleanup(self.repo_root_override.disable)

        self.project = Project.objects.create(name="teste", repo_url="https://github.com/ju/teste")
        self.project.repo_owner, self.project.repo_name = "ju", "teste"
        self.project.save()

        url_patcher = patch(
            "apps.agents.workspace._authenticated_url", return_value=f"file://{self.remote_path}"
        )
        url_patcher.start()
        self.addCleanup(url_patcher.stop)

        gh_client = MagicMock()
        gh_client.get_repo.return_value.default_branch = "main"
        gh_patcher = patch("apps.agents.tasks.get_installation_client", return_value=gh_client)
        gh_patcher.start()
        self.addCleanup(gh_patcher.stop)

        collect_patcher = patch("apps.agents.tasks.collect_status.delay")
        collect_patcher.start()
        self.addCleanup(collect_patcher.stop)

    def test_happy_path_reaches_needs_review(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="Adiciona um comentário")

        run_task_run(task_run.id)

        task_run.refresh_from_db()
        self.assertEqual(task_run.state, TaskRun.State.NEEDS_REVIEW)
        self.assertTrue(task_run.summary)

        steps = list(TaskRunStep.objects.filter(task_run=task_run).order_by("created_at"))
        self.assertEqual([s.phase for s in steps], list(PHASE_ORDER))
        self.assertTrue(all(s.status == TaskRunStep.Status.DONE for s in steps))

        self.assertTrue(
            StatusSnapshot.objects.filter(project=self.project, state=ProjectState.RODANDO).exists()
        )

    def test_missing_task_run_returns_none_without_raising(self):
        result = run_task_run(999999)
        self.assertIsNone(result)

    def test_worktree_failure_lands_in_failed_state(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="teste")
        with patch("apps.agents.tasks.workspace.create_worktree", side_effect=RuntimeError("boom")):
            run_task_run(task_run.id)

        task_run.refresh_from_db()
        self.assertEqual(task_run.state, TaskRun.State.FAILED)
        self.assertTrue(task_run.summary)

    def test_phase_exception_fails_gracefully(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="teste")
        with patch("apps.agents.tasks.agent_client.run_phase", side_effect=RuntimeError("agent broke")):
            run_task_run(task_run.id)

        task_run.refresh_from_db()
        self.assertEqual(task_run.state, TaskRun.State.FAILED)
        failed_steps = TaskRunStep.objects.filter(task_run=task_run, status=TaskRunStep.Status.FAILED)
        self.assertTrue(failed_steps.exists())


class DispatchNightlyQueueTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="teste")

    @patch("apps.agents.tasks.run_task_run.delay")
    @patch("apps.budget.tracking.budget_state", return_value={"should_pause_nightly": True})
    def test_paused_when_budget_over_threshold(self, mock_state, mock_delay):
        from apps.agents.tasks import dispatch_nightly_queue

        TaskRun.objects.create(
            project=self.project, instruction="x", urgency=TaskRun.Urgency.NIGHTLY, state=TaskRun.State.QUEUED
        )
        dispatch_nightly_queue()
        mock_delay.assert_not_called()

    @patch("apps.agents.tasks.run_task_run.delay")
    @patch("apps.budget.tracking.budget_state", return_value={"should_pause_nightly": False})
    def test_dispatches_when_budget_ok(self, mock_state, mock_delay):
        from apps.agents.tasks import dispatch_nightly_queue

        task_run = TaskRun.objects.create(
            project=self.project, instruction="x", urgency=TaskRun.Urgency.NIGHTLY, state=TaskRun.State.QUEUED
        )
        dispatch_nightly_queue()
        mock_delay.assert_called_once_with(task_run.id)
