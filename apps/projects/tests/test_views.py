from unittest.mock import patch

from rest_framework.test import APIClient, APITestCase

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
