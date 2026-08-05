from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.status.tasks import collect_status

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD de projetos (RF-01/02/03).

    TODO(github): detecção automática de stack e vínculo com GitHub App
    entram em fase posterior — por ora o cadastro é manual.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    @action(detail=True, methods=["post"])
    def collect_status(self, request, pk=None):
        """Enfileira a coleta de status para este projeto (RF-04).

        Usado pelo frontend logo após o cadastro, para o projeto aparecer
        no Board sem esperar o próximo ciclo do coletor periódico.
        """
        collect_status.delay(int(pk))
        return Response({"queued": True}, status=202)
