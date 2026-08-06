"""Leitura de repositórios do GitHub App para o cadastro de projetos (RF-01).

Usa o token de instalação já emitido por `apps.status.github_client` — as
permissões atuais da App (`metadata:read`, `contents:write`) bastam para
listar os repositórios da instalação e ler o conteúdo da raiz de cada um.
"""

import base64
import logging

import requests

from apps.status.github_client import get_installation_token

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
TIMEOUT = 20


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
