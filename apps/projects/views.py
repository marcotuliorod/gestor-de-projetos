from rest_framework import viewsets

from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD de projetos (RF-01/02/03).

    TODO(github): detecção automática de stack e vínculo com GitHub App
    entram em fase posterior — por ora o cadastro é manual.
    """

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
