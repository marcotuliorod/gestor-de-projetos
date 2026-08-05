from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.models import Project

from .models import BudgetSettings
from .serializers import BudgetSettingsSerializer
from .tracking import budget_state, current_window_bounds, usage_by_project, weekly_history


class BudgetView(APIView):
    """Estado do orçamento semanal de agentes (RF-11..13) — singleton, sem
    router DRF (não é uma coleção)."""

    def get(self, request):
        state = budget_state()
        start, end = current_window_bounds()
        used_by_project = usage_by_project(start, end)

        projects = Project.objects.filter(id__in=used_by_project.keys())
        distribution = sorted(
            (
                {
                    "project_id": p.id,
                    "project_name": p.name,
                    "used_usd": used_by_project.get(p.id, 0),
                    "priority_weight": p.priority_weight,
                }
                for p in projects
            ),
            key=lambda d: d["used_usd"],
            reverse=True,
        )

        return Response({**state, "distribution": distribution, "weeks": weekly_history()})

    def post(self, request):
        settings_obj = BudgetSettings.load()
        serializer = BudgetSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Reusa get() para devolver a mesma forma (números, não strings de
        # Decimal) que o GET — evita dois formatos diferentes no frontend.
        return self.get(request)
