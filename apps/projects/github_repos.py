"""Leitura de repositórios do GitHub App para o cadastro de projetos (RF-01).

Usa o token de instalação já emitido por `apps.status.github_client` — as
permissões atuais da App (`metadata:read`, `contents:write`) bastam para
listar os repositórios da instalação e ler o conteúdo da raiz de cada um.
"""

import base64
import logging

import requests
from django.conf import settings

from apps.status.github_client import get_installation_token

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
TIMEOUT = 20

# Stack detectada/escolhida -> template de .gitignore do GitHub.
_GITIGNORE_TEMPLATES = {
    "node": "Node",
    "python": "Python",
    "go": "Go",
    "rust": "Rust",
    "php": "Composer",
    "ruby": "Ruby",
    "dart": "Dart",
}


class RepoCreationUnavailable(RuntimeError):
    """GITHUB_PAT não configurado — o fluxo de criar do zero não roda."""


def gitignore_template_for(stack: str) -> str:
    """Template de .gitignore adequado à stack, ou vazio se não reconhecer
    (o GitHub aceita a criação sem template)."""
    first_word = (stack or "").strip().lower().split()[0] if stack.strip() else ""
    return _GITIGNORE_TEMPLATES.get(first_word, "")


def create_repo(name: str, description: str = "", private: bool = True, stack: str = "") -> dict:
    """Cria um repositório na conta do dono do PAT (RF-02).

    `auto_init=True` não é opcional: um repositório vazio não tem branch
    padrão, e `workspace.create_worktree` parte de `origin/<base_branch>`.
    Sem o commit inicial, a tarefa de scaffold falharia na preparação do
    worktree.
    """
    token = getattr(settings, "GITHUB_PAT", "")
    if not token:
        raise RepoCreationUnavailable(
            "Criar projeto do zero exige um token pessoal do GitHub (GITHUB_PAT no .env) — "
            "a App não tem permissão para criar repositórios."
        )

    payload = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": True,
    }
    template = gitignore_template_for(stack)
    if template:
        payload["gitignore_template"] = template

    response = requests.post(
        f"{GITHUB_API}/user/repos",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json=payload,
        timeout=TIMEOUT,
    )
    if response.status_code == 422:
        raise ValueError(f"O GitHub recusou a criação: {response.json().get('message', 'nome já em uso?')}")
    response.raise_for_status()

    repo = response.json()
    return {
        "full_name": repo["full_name"],
        "owner": repo["owner"]["login"],
        "name": repo["name"],
        "html_url": repo["html_url"],
        "private": repo["private"],
        "default_branch": repo.get("default_branch") or "main",
    }


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_installation_token()}",
        "Accept": "application/vnd.github+json",
    }


def list_installation_repos() -> list[dict]:
    """Repositórios onde a GitHub App está instalada, para o seletor do
    cadastro (RF-01). Ordenados do mais recentemente atualizado para o mais
    antigo — é a ordem útil para quem está cadastrando um projeto."""
    response = requests.get(
        f"{GITHUB_API}/installation/repositories",
        headers=_headers(),
        params={"per_page": 100},
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    repos = [
        {
            "full_name": repo["full_name"],
            "owner": repo["owner"]["login"],
            "name": repo["name"],
            "private": repo["private"],
            "language": repo.get("language") or "",
            "description": repo.get("description") or "",
            "updated_at": repo.get("updated_at") or "",
            "html_url": repo["html_url"],
        }
        for repo in response.json().get("repositories", [])
    ]
    repos.sort(key=lambda r: r["updated_at"], reverse=True)
    return repos


def list_files(owner: str, repo: str, path: str = "") -> list[str]:
    """Nomes dos arquivos/pastas em `path` (raiz por padrão). Lista vazia
    quando o caminho não existe ou o repositório está vazio (recém-criado,
    sem commit) — a API responde 404 nos dois casos, o que não é erro para
    o nosso uso."""
    response = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(),
        timeout=TIMEOUT,
    )
    if response.status_code == 404:
        return []
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):  # caminho aponta para um arquivo, não pasta
        return []
    return [entry["name"] for entry in payload]


def read_text_file(owner: str, repo: str, path: str) -> str | None:
    """Conteúdo de um arquivo de texto da raiz, ou None se não existir."""
    response = requests.get(
        f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
        headers=_headers(),
        timeout=TIMEOUT,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if payload.get("encoding") != "base64":
        return None
    return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
