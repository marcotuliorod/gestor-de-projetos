from datetime import datetime, timedelta, timezone as dt_timezone

from rest_framework.test import APIClient, APITestCase

from apps.projects.models import Project
from apps.status.models import ProjectState, StatusSnapshot


def _snapshot_at(project, state, when):
    snap = StatusSnapshot.objects.create(project=project, state=state)
    StatusSnapshot.objects.filter(pk=snap.pk).update(created_at=when)
    return snap


class BoardViewTests(APITestCase):
    """Regressão-alvo: BoardView usa `.distinct("project_id")` (DISTINCT ON),
    um recurso exclusivo do Postgres sem equivalente em SQLite — este teste
    só é significativo rodando contra Postgres de verdade (ver CI)."""

    def setUp(self):
        self.client = APIClient()

    def test_returns_only_latest_snapshot_per_project(self):
        project_a = Project.objects.create(name="a")
        older = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
        newer = older + timedelta(hours=1)

        _snapshot_at(project_a, ProjectState.EM_DIA, older)
        latest = _snapshot_at(project_a, ProjectState.PRECISA_DE_VOCE, newer)

        response = self.client.get("/api/board/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], latest.id)
        self.assertEqual(response.data[0]["state"], "precisa_de_voce")

    def test_orders_by_urgency_then_name(self):
        project_healthy = Project.objects.create(name="z-healthy")
        project_attention = Project.objects.create(name="a-attention")
        project_running = Project.objects.create(name="m-running")

        now = datetime(2026, 1, 1, tzinfo=dt_timezone.utc)
        _snapshot_at(project_healthy, ProjectState.EM_DIA, now)
        _snapshot_at(project_attention, ProjectState.PRECISA_DE_VOCE, now)
        _snapshot_at(project_running, ProjectState.RODANDO, now)

        response = self.client.get("/api/board/")

        states = [row["state"] for row in response.data]
        self.assertEqual(states, ["precisa_de_voce", "rodando", "em_dia"])

    def test_empty_board_returns_empty_list(self):
        response = self.client.get("/api/board/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
