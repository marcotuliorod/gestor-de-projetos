import logging

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.agents.models import TaskRun
from apps.agents.tasks import run_task_run
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

    @action(detail=False, methods=["post"], url_path="create-from-scratch")
    def create_from_scratch(self, request):
        """Cria o repositório no GitHub, cadastra o projeto e dispara a
        primeira tarefa de scaffold (RF-02).

        O scaffold segue o mesmo caminho de qualquer tarefa: vai até a
        revisão e só vira PR depois que você aprova (RNF-01/RF-10). Um
        repositório novo não é exceção à regra de nunca escrever direto na
        branch padrão.
        """
        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"detail": "Informe um nome para o projeto."}, status=400)
        if Project.objects.filter(name__iexact=name).exists():
            return Response({"detail": "Já existe um projeto com esse nome."}, status=400)

        description = str(request.data.get("description", "")).strip()
        stack = str(request.data.get("stack", "")).strip()
        private = bool(request.data.get("private", True))
        # "Deixar o agente sugerir" chega como stack vazia — nesse caso não
        # pré-preenchemos comandos, o scaffold é que vai definir a stack.
        suggested = stack_detect.suggest_for_stack(stack) if stack else {}

        try:
            repo = github_repos.create_repo(name=name, description=description, private=private, stack=stack)
        except github_repos.RepoCreationUnavailable as exc:
            return Response({"detail": str(exc)}, status=409)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception:
            logger.exception("create_from_scratch: falha ao criar repositório %s", name)
            return Response({"detail": "Não consegui criar o repositório no GitHub — ver logs."}, status=502)

        project = Project.objects.create(
            name=name,
            description=description,
            repo_url=repo["html_url"],
            stack=suggested.get("stack", stack),
            build_command=suggested.get("build_command", ""),
            test_command=suggested.get("test_command", ""),
            lint_command=suggested.get("lint_command", ""),
        )

        task_run = TaskRun.objects.create(
            project=project,
            instruction=_scaffold_instruction(name, description, stack),
            urgency=TaskRun.Urgency.NOW,
        )
        run_task_run.delay(task_run.id)

        return Response(
            {
                "project": ProjectSerializer(project).data,
                "task_run_id": task_run.id,
                "repo_url": repo["html_url"],
            },
            status=201,
        )


def _scaffold_instruction(name: str, description: str, stack: str) -> str:
    """Instrução da primeira tarefa de um projeto criado do zero.

    O repositório já nasce com commit inicial, licença e .gitignore da
    stack (feitos na criação via API) — o agente cuida do resto.
    """
    alvo = stack or "a stack que fizer mais sentido para o objetivo descrito (justifique a escolha)"
    proposito = description or "(sem descrição — proponha algo coerente com o nome do projeto)"
    return (
        f"Este repositório acabou de ser criado e está praticamente vazio. "
        f"Monte o scaffold inicial do projeto '{name}'.\n\n"
        f"Propósito: {proposito}\n"
        f"Stack: {alvo}\n\n"
        "Entregue:\n"
        "- estrutura de pastas condizente com a stack\n"
        "- README com o propósito do projeto e como rodar localmente\n"
        "- configuração de lint/formatação\n"
        "- workflow de CI no GitHub Actions rodando build, teste e lint\n"
        "- complete o .gitignore se faltar algo específico da stack\n\n"
        "Mantenha o scaffold enxuto e funcional: nada de código de exemplo além do mínimo "
        "necessário para a CI passar de verdade."
    )

    @action(detail=True, methods=["post"])
    def collect_status(self, request, pk=None):
        """Enfileira a coleta de status para este projeto (RF-04).

        Usado pelo frontend logo após o cadastro, para o projeto aparecer
        no Board sem esperar o próximo ciclo do coletor periódico.
        """
        collect_status.delay(int(pk))
        return Response({"queued": True}, status=202)
