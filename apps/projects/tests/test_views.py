from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.agents.models import TaskRun
from apps.projects import github_repos
from apps.projects.models import Project

_REPOS = [
    {
        "full_name": "ju/api-financeiro",
        "owner": "ju",
        "name": "api-financeiro",
        "private": True,
        "language": "TypeScript",
        "description": "",
        "updated_at": "2026-08-01T00:00:00Z",
        "html_url": "https://github.com/ju/api-financeiro",
    },
    {
        "full_name": "ju/loja-mirim",
        "owner": "ju",
        "name": "loja-mirim",
        "private": False,
        "language": "Python",
        "description": "",
        "updated_at": "2026-07-01T00:00:00Z",
        "html_url": "https://github.com/ju/loja-mirim",
    },
]


class AvailableReposTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("apps.projects.views.github_repos.list_installation_repos", return_value=_REPOS)
    def test_lists_repos_and_flags_already_added(self, mock_list):
        project = Project.objects.create(name="api", repo_url="https://github.com/ju/api-financeiro")
        self.assertEqual(project.repo_owner, "ju")  # derivado no save()

        response = self.client.get("/api/projects/available-repos/")

        self.assertEqual(response.status_code, 200)
        by_name = {r["full_name"]: r for r in response.data}
        self.assertTrue(by_name["ju/api-financeiro"]["already_added"])
        self.assertFalse(by_name["ju/loja-mirim"]["already_added"])

    @patch("apps.projects.views.github_repos.list_installation_repos", side_effect=RuntimeError("sem rede"))
    def test_github_failure_returns_502_not_500(self, mock_list):
        response = self.client.get("/api/projects/available-repos/")
        self.assertEqual(response.status_code, 502)
        self.assertIn("detail", response.data)


class DetectStackViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.detected = {
            "stack": "Node · Vite",
            "build_command": "npm run build",
            "test_command": "",
            "lint_command": "npm run lint",
            "detected_from": ["package.json"],
        }

    @patch("apps.projects.views.stack_detect.detect_stack")
    def test_accepts_owner_and_name(self, mock_detect):
        mock_detect.return_value = dict(self.detected)

        response = self.client.post(
            "/api/projects/detect-stack/", {"owner": "ju", "name": "painel"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        mock_detect.assert_called_once_with("ju", "painel")
        self.assertEqual(response.data["stack"], "Node · Vite")
        self.assertEqual(response.data["repo_url"], "https://github.com/ju/painel")

    @patch("apps.projects.views.stack_detect.detect_stack")
    def test_accepts_pasted_url(self, mock_detect):
        mock_detect.return_value = dict(self.detected)

        response = self.client.post(
            "/api/projects/detect-stack/",
            {"repo_url": "https://github.com/ju/painel.git"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        mock_detect.assert_called_once_with("ju", "painel")

    def test_rejects_unparseable_url(self):
        response = self.client.post(
            "/api/projects/detect-stack/", {"repo_url": "não é uma url"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    @patch(
        "apps.projects.views.stack_detect.detect_stack",
        side_effect=RuntimeError("403 do GitHub"),
    )
    def test_unreadable_repo_returns_502(self, mock_detect):
        response = self.client.post(
            "/api/projects/detect-stack/", {"owner": "ju", "name": "privado"}, format="json"
        )
        self.assertEqual(response.status_code, 502)


_CREATED_REPO = {
    "full_name": "ju/novo-projeto",
    "owner": "ju",
    "name": "novo-projeto",
    "html_url": "https://github.com/ju/novo-projeto",
    "private": True,
    "default_branch": "main",
}


class CreateFromScratchTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("apps.projects.views.run_task_run.delay")
    @patch("apps.projects.views.github_repos.create_repo", return_value=_CREATED_REPO)
    def test_creates_repo_project_and_scaffold_task(self, mock_create, mock_delay):
        response = self.client.post(
            "/api/projects/create-from-scratch/",
            {"name": "novo-projeto", "description": "Um painel", "stack": "Go", "private": True},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        project = Project.objects.get(name="novo-projeto")
        self.assertEqual(project.repo_url, "https://github.com/ju/novo-projeto")
        # A stack escolhida vira comandos sem precisar ler o repositório.
        self.assertEqual(project.test_command, "go test ./...")

        task_run = TaskRun.objects.get(project=project)
        self.assertEqual(response.data["task_run_id"], task_run.id)
        mock_delay.assert_called_once_with(task_run.id)
        self.assertIn("scaffold", task_run.instruction.lower())

    @patch("apps.projects.views.run_task_run.delay")
    @patch("apps.projects.views.github_repos.create_repo", return_value=_CREATED_REPO)
    def test_agent_suggested_stack_leaves_commands_blank(self, mock_create, mock_delay):
        """'Deixar o agente sugerir' chega como stack vazia — pré-preencher
        comandos aqui seria inventar."""
        response = self.client.post(
            "/api/projects/create-from-scratch/", {"name": "sem-stack"}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        project = Project.objects.get(name="sem-stack")
        self.assertEqual(project.stack, "")
        self.assertEqual(project.build_command, "")

    @patch(
        "apps.projects.views.github_repos.create_repo",
        side_effect=github_repos.RepoCreationUnavailable("faltou o GITHUB_PAT"),
    )
    def test_without_pat_returns_409_and_creates_nothing(self, mock_create):
        response = self.client.post(
            "/api/projects/create-from-scratch/", {"name": "sem-token"}, format="json"
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("GITHUB_PAT", response.data["detail"])
        self.assertFalse(Project.objects.filter(name="sem-token").exists())

    def test_rejects_duplicate_name_before_touching_github(self):
        Project.objects.create(name="Repetido")

        with patch("apps.projects.views.github_repos.create_repo") as mock_create:
            response = self.client.post(
                "/api/projects/create-from-scratch/", {"name": "repetido"}, format="json"
            )

        self.assertEqual(response.status_code, 400)
        mock_create.assert_not_called()

    def test_rejects_empty_name(self):
        response = self.client.post("/api/projects/create-from-scratch/", {"name": "  "}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch(
        "apps.projects.views.github_repos.create_repo",
        side_effect=ValueError("name already exists on this account"),
    )
    def test_github_refusal_surfaces_as_400(self, mock_create):
        response = self.client.post(
            "/api/projects/create-from-scratch/", {"name": "ja-existe-no-github"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Project.objects.filter(name="ja-existe-no-github").exists())


class CreateRepoTests(APITestCase):
    @override_settings(GITHUB_PAT="")
    def test_missing_pat_raises_a_typed_error(self):
        with self.assertRaises(github_repos.RepoCreationUnavailable):
            github_repos.create_repo(name="x")

    @override_settings(GITHUB_PAT="token-de-teste")
    @patch("apps.projects.github_repos.requests.post")
    def test_auto_init_is_always_sent(self, mock_post):
        """Sem commit inicial o repositório não tem branch padrão, e a
        preparação do worktree da tarefa de scaffold falharia."""
        mock_post.return_value.status_code = 201
        mock_post.return_value.json.return_value = {
            "full_name": "ju/x",
            "owner": {"login": "ju"},
            "name": "x",
            "html_url": "https://github.com/ju/x",
            "private": True,
            "default_branch": "main",
        }

        github_repos.create_repo(name="x", stack="Python · Django")

        payload = mock_post.call_args.kwargs["json"]
        self.assertTrue(payload["auto_init"])
        self.assertEqual(payload["gitignore_template"], "Python")


class GitignoreTemplateTests(APITestCase):
    def test_maps_known_stacks(self):
        self.assertEqual(github_repos.gitignore_template_for("Node · Vite"), "Node")
        self.assertEqual(github_repos.gitignore_template_for("Python · FastAPI"), "Python")
        self.assertEqual(github_repos.gitignore_template_for("Go"), "Go")

    def test_unknown_stack_yields_no_template(self):
        self.assertEqual(github_repos.gitignore_template_for("COBOL"), "")
        self.assertEqual(github_repos.gitignore_template_for(""), "")
