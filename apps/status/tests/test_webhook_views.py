import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import Client, TestCase, override_settings

from apps.projects.models import Project

SECRET = "test-webhook-secret"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


@override_settings(GITHUB_WEBHOOK_SECRET=SECRET)
class GithubWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.project = Project.objects.create(name="teste", repo_url="https://github.com/ju/teste")

    @patch("apps.status.webhook_views.collect_status.delay")
    def test_valid_signature_triggers_collect(self, mock_delay):
        body = json.dumps({"repository": {"full_name": "ju/teste"}}).encode()
        response = self.client.post(
            "/api/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
            HTTP_X_GITHUB_EVENT="push",
        )
        self.assertEqual(response.status_code, 202)
        mock_delay.assert_called_once_with(self.project.id)

    @patch("apps.status.webhook_views.collect_status.delay")
    def test_invalid_signature_rejected(self, mock_delay):
        body = json.dumps({"repository": {"full_name": "ju/teste"}}).encode()
        response = self.client.post(
            "/api/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=deadbeef",
            HTTP_X_GITHUB_EVENT="push",
        )
        self.assertEqual(response.status_code, 403)
        mock_delay.assert_not_called()

    @patch("apps.status.webhook_views.collect_status.delay")
    def test_irrelevant_event_ignored(self, mock_delay):
        body = json.dumps({"repository": {"full_name": "ju/teste"}}).encode()
        response = self.client.post(
            "/api/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
            HTTP_X_GITHUB_EVENT="star",
        )
        self.assertEqual(response.status_code, 204)
        mock_delay.assert_not_called()

    @patch("apps.status.webhook_views.collect_status.delay")
    def test_unknown_repo_still_acked(self, mock_delay):
        body = json.dumps({"repository": {"full_name": "someone/else"}}).encode()
        response = self.client.post(
            "/api/webhooks/github/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign(body),
            HTTP_X_GITHUB_EVENT="push",
        )
        self.assertEqual(response.status_code, 202)
        mock_delay.assert_not_called()
