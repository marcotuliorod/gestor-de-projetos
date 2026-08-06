import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.status.tasks import collect_status

from . import github_repos, stack_detect
from .github_utils import parse_github_repo_url
from .models import Project
from .serializers import ProjectSerializer

logger = logging.getLogger(__name__)


class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD de projetos (RF-01/02/03)."""

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    @action(detail=False, methods=["get"], url_path="available-repos")
    def available_repos(self, request):
        """Repositórios onde a GitHub App está instalada, para o seletor do
        cadastro (RF-01). Marca os que já estão cadastrados para a UI poder
        desabilitá-los em vez de deixar o usuário criar duplicata."""
        try:
            repos = github_repos.list_installation_repos()
        except Exception:
            logger.exception("available_repos: falha ao listar repositórios da instalação")
            return Response(
                {"detail": "Não consegui listar seus repositórios do GitHub — confira as credenciais da App."},
                status=502,
            )

        already = {
            (owner.lower(), name.lower())
            for owner, name in Project.objects.exclude(repo_owner="").values_list("repo_owner", "repo_name")
        }
        for repo in repos:
            repo["already_added"] = (repo["owner"].lower(), repo["name"].lower()) in already
        return Response(repos)

    @action(detail=False, methods=["post"], url_path="detect-stack")
    def detect_stack(self, request):
        """Detecta stack e sugere comandos para um repositório (RF-01).

        Aceita `repo_url` (colada à mão) ou `owner`+`name` (vindos do
        seletor). Nada é gravado aqui — o usuário ainda confirma na tela.
        """
        owner = (request.data.get("owner") or "").strip()
        name = (request.data.get("name") or "").strip()
        if not (owner and name):
            parsed = parse_github_repo_url(str(request.data.get("repo_url", "")))
            if not parsed:
                return Response(
                    {"detail": "Informe owner e name, ou uma URL de repositório do GitHub válida."},
                    status=400,
                )
            owner, name = parsed

        try:
            detected = stack_detect.detect_stack(owner, name)
        except Exception:
            logger.exception("detect_stack: falha ao analisar %s/%s", owner, name)
            return Response(
                {"detail": "Não consegui ler esse repositório — confira se a App tem acesso a ele."},
                status=502,
            )

        detected.update(owner=owner, name=name, repo_url=f"https://github.com/{owner}/{name}")
        return Response(detected)

    @action(detail=True, methods=["post"])
    def collect_status(self, request, pk=None):
        """Enfileira a coleta de status para este projeto (RF-04).

        Usado pelo frontend logo após o cadastro, para o projeto aparecer
        no Board sem esperar o próximo ciclo do coletor periódico.
        """
        collect_status.delay(int(pk))
        return Response({"queued": True}, status=202)
