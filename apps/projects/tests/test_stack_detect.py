import json
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.projects import stack_detect


def _package_json(deps=None, dev=None, scripts=None) -> str:
    return json.dumps(
        {
            "dependencies": deps or {},
            "devDependencies": dev or {},
            "scripts": scripts or {},
        }
    )


class DetectNodeTests(SimpleTestCase):
    def test_framework_and_real_scripts(self):
        result = stack_detect._detect_node(
            ["package.json", "package-lock.json"],
            _package_json(deps={"react": "19", "vite": "8"}, scripts={"build": "vite build", "lint": "oxlint"}),
        )
        # `vite` vem antes de `react` na tabela — o mais específico vence.
        self.assertEqual(result["stack"], "Node · Vite")
        self.assertEqual(result["build_command"], "npm run build")
        self.assertEqual(result["lint_command"], "npm run lint")

    def test_only_suggests_scripts_that_exist(self):
        """Sugerir `npm test` num projeto sem script de teste mandaria o
        usuário rodar um comando que falha."""
        result = stack_detect._detect_node(["package.json"], _package_json(scripts={"build": "tsc"}))
        self.assertEqual(result["build_command"], "npm run build")
        self.assertEqual(result["test_command"], "")
        self.assertEqual(result["lint_command"], "")

    def test_package_manager_from_lockfile(self):
        result = stack_detect._detect_node(
            ["package.json", "pnpm-lock.yaml"], _package_json(scripts={"build": "x", "test": "y"})
        )
        self.assertEqual(result["build_command"], "pnpm run build")
        self.assertEqual(result["test_command"], "pnpm run test")

    def test_invalid_package_json_does_not_raise(self):
        result = stack_detect._detect_node(["package.json"], "{ isto não é json }")
        self.assertEqual(result["stack"], "Node")
        self.assertEqual(result["build_command"], "")

    def test_framework_found_in_dev_dependencies(self):
        result = stack_detect._detect_node(["package.json"], _package_json(dev={"astro": "4"}))
        self.assertEqual(result["stack"], "Node · Astro")


class DetectPythonTests(SimpleTestCase):
    def test_django_with_pytest_and_ruff(self):
        result = stack_detect._detect_python(
            ["pyproject.toml", "manage.py"],
            "[project]\ndependencies = ['django', 'pytest', 'ruff']",
            None,
        )
        self.assertEqual(result["stack"], "Python · Django")
        self.assertEqual(result["test_command"], "pytest")
        self.assertEqual(result["lint_command"], "ruff check .")

    def test_django_without_pytest_falls_back_to_manage_py(self):
        result = stack_detect._detect_python(["requirements.txt", "manage.py"], None, "django==5.1\n")
        self.assertEqual(result["test_command"], "python manage.py test")
        self.assertEqual(result["build_command"], "pip install -r requirements.txt")

    def test_uv_lock_wins_over_requirements(self):
        result = stack_detect._detect_python(["requirements.txt", "uv.lock"], None, "fastapi\n")
        self.assertEqual(result["build_command"], "uv sync")
        self.assertEqual(result["stack"], "Python · FastAPI")

    def test_poetry_detected_from_pyproject_section(self):
        result = stack_detect._detect_python(["pyproject.toml"], "[tool.poetry]\nname='x'", None)
        self.assertEqual(result["build_command"], "poetry install")


class DetectSimpleTests(SimpleTestCase):
    def test_go_conventional_commands(self):
        result = stack_detect._detect_simple("Go", ["go.mod"])
        self.assertEqual(result["stack"], "Go")
        self.assertEqual(result["test_command"], "go test ./...")


class DetectStackEntrypointTests(SimpleTestCase):
    def test_repo_without_known_manifest_returns_empty(self):
        with patch.object(stack_detect.github_repos, "list_files", return_value=["README.md", "LICENSE"]):
            result = stack_detect.detect_stack("ju", "so-docs")
        self.assertEqual(result["stack"], "")
        self.assertEqual(result["build_command"], "")
        self.assertIn("README.md", result["detected_from"])

    def test_empty_repo_returns_empty(self):
        """Repositório recém-criado sem commit — a API devolve 404 e
        `list_files` normaliza para lista vazia."""
        with patch.object(stack_detect.github_repos, "list_files", return_value=[]):
            result = stack_detect.detect_stack("ju", "vazio")
        self.assertEqual(result["stack"], "")

    def test_routes_node_repo_to_node_detection(self):
        with (
            patch.object(stack_detect.github_repos, "list_files", return_value=["package.json"]),
            patch.object(
                stack_detect.github_repos,
                "read_text_file",
                return_value=_package_json(deps={"fastify": "4"}, scripts={"test": "vitest"}),
            ),
        ):
            result = stack_detect.detect_stack("ju", "api")
        self.assertEqual(result["stack"], "Node · Fastify")
        self.assertEqual(result["test_command"], "npm run test")
        self.assertEqual(result["subdir"], "")


class MonorepoDetectionTests(SimpleTestCase):
    """Caso real: `Pra_Lattes_Updater` guarda os manifestos em `backend/` e
    `frontend/`, com a raiz só de documentação — sem isso a detecção
    devolvia vazio para um repositório perfeitamente reconhecível."""

    def _list_files(self, owner, repo, path=""):
        if path == "":
            return ["README.md", "adr", "backend", "frontend", "docs"]
        if path == "backend":
            return ["pyproject.toml", "manage.py"]
        return []

    def test_finds_manifest_one_level_down(self):
        with (
            patch.object(stack_detect.github_repos, "list_files", side_effect=self._list_files),
            patch.object(
                stack_detect.github_repos,
                "read_text_file",
                return_value="[project]\ndependencies = ['django', 'pytest']",
            ),
        ):
            result = stack_detect.detect_stack("ju", "monorepo")

        self.assertEqual(result["stack"], "Python · Django")
        self.assertEqual(result["subdir"], "backend")

    def test_commands_are_prefixed_with_the_subdir(self):
        """O worktree do agente abre na raiz do repositório — `pytest` cru
        não acharia o projeto."""
        with (
            patch.object(stack_detect.github_repos, "list_files", side_effect=self._list_files),
            patch.object(
                stack_detect.github_repos,
                "read_text_file",
                return_value="[project]\ndependencies = ['django', 'pytest']",
            ),
        ):
            result = stack_detect.detect_stack("ju", "monorepo")

        self.assertEqual(result["test_command"], "cd backend && pytest")

    def test_root_manifest_wins_over_subdir(self):
        def only_root(owner, repo, path=""):
            return ["go.mod", "backend"] if path == "" else ["package.json"]

        with patch.object(stack_detect.github_repos, "list_files", side_effect=only_root):
            result = stack_detect.detect_stack("ju", "go-com-frontend")

        self.assertEqual(result["stack"], "Go")
        self.assertEqual(result["subdir"], "")
        self.assertEqual(result["test_command"], "go test ./...")


class SuggestForStackTests(SimpleTestCase):
    def test_python_choice(self):
        result = stack_detect.suggest_for_stack("Python · FastAPI")
        self.assertEqual(result["test_command"], "pytest")

    def test_go_choice(self):
        result = stack_detect.suggest_for_stack("Go")
        self.assertEqual(result["build_command"], "go build ./...")

    def test_node_is_the_default(self):
        result = stack_detect.suggest_for_stack("Node · Fastify")
        self.assertEqual(result["build_command"], "npm run build")
