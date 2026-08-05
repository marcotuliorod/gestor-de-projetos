import re

_GITHUB_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?/?$"
)


def parse_github_repo_url(url: str) -> tuple[str, str] | None:
    """Extrai (owner, repo) de uma URL do GitHub, ou None se não reconhecer.

    Cobre variações comuns: com/sem esquema, sufixo .git, barra final.
    """
    if not url:
        return None
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        return None
    return match.group(1), match.group(2)
