from rest_framework import generics

from .models import STATE_URGENCY, StatusSnapshot
from .serializers import StatusSnapshotSerializer


class BoardView(generics.ListAPIView):
    """Board read-only (RF-04/05): o snapshot mais recente por projeto,
    ordenado por urgência do estado.
    """

    serializer_class = StatusSnapshotSerializer
    pagination_class = None

    def get_queryset(self):
        # DISTINCT ON (Postgres) pega o snapshot mais novo de cada projeto.
        latest = (
            StatusSnapshot.objects.order_by("project_id", "-created_at")
            .distinct("project_id")
            .select_related("project")
        )
        # Ordena por urgência do estado (mais urgente primeiro), depois nome.
        return sorted(
            latest,
            key=lambda s: (STATE_URGENCY.get(s.state, 99), s.project.name),
        )
