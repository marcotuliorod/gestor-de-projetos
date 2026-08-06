import subprocess
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.agents import workspace
from apps.agents.models import TaskRun
from apps.projects.models import Project


def _run(cmd, cwd=None):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


class WorkspaceTests(TestCase):
    """Usa um repo git local (não o GitHub) como 'remoto', evitando
    qualquer chamada de rede/credencial real — `_authenticated_url` é
    trocado por um caminho `file://` local via monkeypatch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)

        self.remote_path = base / "remote.git"
        _run(["git", "init", "--bare", "-b", "main", str(self.remote_path)])

        seed = base / "seed"
        seed.mkdir()
        _run(["git", "init", "-b", "main", str(seed)])
        _run(["git", "config", "user.email", "t@example.com"], cwd=seed)
        _run(["git", "config", "user.name", "t"], cwd=seed)
        (seed / "README.md").write_text("hello\n")
        _run(["git", "add", "."], cwd=seed)
        _run(["git", "commit", "-m", "init"], cwd=seed)
        _run(["git", "remote", "add", "origin", str(self.remote_path)], cwd=seed)
        _run(["git", "push", "origin", "main"], cwd=seed)

        self.repo_root = base / "repos"
        self.override = override_settings(AGENTS_REPO_ROOT=str(self.repo_root))
        self.override.enable()
        self.addCleanup(self.override.disable)

        self.project = Project.objects.create(
            name="teste", repo_url="https://github.com/ju/teste"
        )
        self.project.repo_owner, self.project.repo_name = "ju", "teste"
        self.project.save()

        patcher = patch(
            "apps.agents.workspace._authenticated_url",
            return_value=f"file://{self.remote_path}",
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ensure_mirror_clones_then_fetches(self):
        mirror = workspace.ensure_mirror(self.project)
        self.assertTrue(mirror.exists())
        # Segunda chamada deve reaproveitar o mirror (fetch, não re-clone).
        mirror2 = workspace.ensure_mirror(self.project)
        self.assertEqual(mirror, mirror2)

    def test_create_worktree_creates_branch_and_files(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="teste")
        worktree = workspace.create_worktree(task_run, base_branch="main")
        self.assertTrue((worktree / "README.md").exists())
        result = subprocess.run(
            ["git", "branch", "--show-current"], cwd=worktree, capture_output=True, text=True, check=True
        )
        self.assertEqual(result.stdout.strip(), f"agent/task-{task_run.id}")

    def test_commit_worktree_changes_commits_uncommitted_edits(self):
        """Regressão: o agente (Edit/Write) só escreve nos arquivos, nunca
        commita — sem commit_worktree_changes, diff_stat()/push_branch()
        não veem a mudança (comparam commits, não o working tree), e um
        approve produziria um PR vazio. Confirmado por teste real contra a
        API antes deste fix existir."""
        task_run = TaskRun.objects.create(project=self.project, instruction="teste", base_branch="main")
        worktree = workspace.create_worktree(task_run, base_branch="main")

        (worktree / "README.md").write_text("mudança sem commit\n")
        committed = workspace.commit_worktree_changes(task_run, "Execute: teste")
        self.assertTrue(committed)

        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=True
        )
        self.assertEqual(status.stdout.strip(), "")  # working tree limpo após o commit

        files = workspace.diff_stat(task_run)
        self.assertEqual([f["path"] for f in files], ["README.md"])

    def test_commit_worktree_changes_noop_when_nothing_pending(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="teste", base_branch="main")
        workspace.create_worktree(task_run, base_branch="main")

        committed = workspace.commit_worktree_changes(task_run, "não deveria commitar nada")
        self.assertFalse(committed)

    def test_diff_stat_reflects_change(self):
        task_run = TaskRun.objects.create(
            project=self.project, instruction="teste", base_branch="main"
        )
        worktree = workspace.create_worktree(task_run, base_branch="main")
        (worktree / "NOVO.md").write_text("conteúdo novo\n")
        # Usa o helper de produção (já configura identidade do commit via
        # -c) em vez de `git commit` cru — o ambiente de teste (CI, container
        # non-root) pode não ter user.name/email git configurados global.
        workspace.commit_worktree_changes(task_run, "novo arquivo")

        files = workspace.diff_stat(task_run)
        paths = [f["path"] for f in files]
        self.assertIn("NOVO.md", paths)
        novo = next(f for f in files if f["path"] == "NOVO.md")
        self.assertEqual(novo["added"], 1)
        self.assertEqual(novo["removed"], 0)

    def test_create_worktree_same_project_concurrent_is_safe(self):
        """Regressão RF-21: sem o lock por projeto em `_project_git_lock`,
        duas TaskRuns do mesmo projeto chamando create_worktree ao mesmo
        tempo competem pelos lockfiles internos do mirror compartilhado.
        Injeta um sleep real dentro de ensure_mirror para forçar a
        sobreposição (sem isso, as chamadas são rápidas demais para colidir
        de forma confiável em um teste)."""
        real_ensure_mirror = workspace.ensure_mirror

        def slow_ensure_mirror(project):
            result = real_ensure_mirror(project)
            time.sleep(0.3)
            return result

        task_run_a = TaskRun.objects.create(project=self.project, instruction="a", base_branch="main")
        task_run_b = TaskRun.objects.create(project=self.project, instruction="b", base_branch="main")

        errors = []
        results = {}

        def worker(task_run, key):
            try:
                results[key] = workspace.create_worktree(task_run, base_branch="main")
            except Exception as exc:
                errors.append(exc)

        with patch("apps.agents.workspace.ensure_mirror", side_effect=slow_ensure_mirror):
            t1 = threading.Thread(target=worker, args=(task_run_a, "a"))
            t2 = threading.Thread(target=worker, args=(task_run_b, "b"))
            t1.start()
            time.sleep(0.05)  # garante que t1 entra no lock primeiro
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

        self.assertEqual(errors, [])
        self.assertTrue(results["a"].exists())
        self.assertTrue(results["b"].exists())

    def test_discard_worktree_removes_branch(self):
        task_run = TaskRun.objects.create(project=self.project, instruction="teste")
        worktree = workspace.create_worktree(task_run, base_branch="main")
        task_run.branch_name = f"agent/task-{task_run.id}"

        workspace.discard_worktree(task_run)
        self.assertFalse(worktree.exists())
