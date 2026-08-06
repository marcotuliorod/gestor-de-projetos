import base64
import re

import github
from django.conf import settings

# Cobertura só é reportada quando o CI do projeto publica o número no
# output do check-run (RF-04: "quando disponível"). Exige a palavra
# "cover"/"cobertura" perto do percentual — um texto de check-run tem
# vários números soltos, e pegar qualquer "%" daria um valor errado com
# cara de certo.
_COVERAGE_RE = re.compile(
    r"(?:cover(?:age)?|cobertura)\D{0,20}?(\d{1,3}(?:[.,]\d+)?)\s*%"
    r"|(\d{1,3}(?:[.,]\d+)?)\s*%\D{0,20}?(?:cover(?:age)?|cobertura)",
    re.IGNORECASE,
)


def _extract_coverage(check_runs) -> float | None:
    """Percentual de cobertura publicado por algum check-run, ou None.

    Varre título e resumo de cada check-run; o primeiro valor plausível
    (0–100) vence.
    """
    for run in check_runs:
        output = getattr(run, "output", None)
        for field in ("title", "summary"):
            text = getattr(output, field, None) if output else None
            if not text:
                continue
            match = _COVERAGE_RE.search(text)
            if not match:
                continue
            raw = match.group(1) or match.group(2)
            try:
                value = float(raw.replace(",", "."))
            except ValueError:
                continue
            if 0 <= value <= 100:
                return round(value, 1)
    return None


def get_installation_token(installation_id: str | None = None) -> str:
    """Autentica a GitHub App (JWT RS256) e troca por um installation
    access token, retornando a string do token — usada como credencial
    HTTPS do git (clone/fetch/push) pelo módulo de worktrees dos agentes.
    """
    private_key = base64.b64decode(settings.GITHUB_APP_PRIVATE_KEY_B64).decode()
    integration = github.GithubIntegration(settings.GITHUB_APP_ID, private_key)
    inst_id = int(installation_id or settings.GITHUB_APP_INSTALLATION_ID)
    return integration.get_access_token(inst_id).token


def get_installation_client(installation_id: str | None = None) -> github.Github:
    """Mesma troca de token, retornando um client PyGithub já escopado a
    essa instalação (para chamadas REST)."""
    token = get_installation_token(installation_id)
    return github.Github(auth=github.Auth.Token(token))


def collect_repo_status(gh: github.Github, owner: str, repo_name: str) -> dict:
    """Consulta a API do GitHub (sem clone local) e retorna um dict pronto
    para virar os campos de um StatusSnapshot.

    ahead/behind e changed_files só são significativos quando há PR aberto
    (comparados contra a base do PR mais recente) — sem PR aberto, ficam 0.
    """
    repo = gh.get_repo(f"{owner}/{repo_name}")
    default_branch = repo.default_branch
    branch_commit = repo.get_branch(default_branch).commit

    last_commit = branch_commit.sha[:7]
    message = branch_commit.commit.message.splitlines()[0] if branch_commit.commit.message else ""
    if message:
        last_commit = f"{last_commit} {message}"

    open_prs = list(repo.get_pulls(state="open"))

    # Os check-runs alimentam tanto o fallback de ci_status quanto a lista
    # detalhada e a cobertura (RF-04), então são buscados sempre.
    check_runs = list(branch_commit.get_check_runs())
    checks = [
        {
            "name": run.name,
            "conclusion": run.conclusion or "",
            "status": run.status or "",
        }
        for run in check_runs
    ]
    coverage_pct = _extract_coverage(check_runs)

    # A API de status combinado devolve "pending" para commits que não têm
    # *nenhum* commit status — e projetos que usam só GitHub Actions (check
    # runs) nunca têm. Sem olhar total_count, um repositório com todo o CI
    # verde aparecia como "pending".
    combined_status = branch_commit.get_combined_status()
    has_statuses = bool(combined_status) and getattr(combined_status, "total_count", 0) > 0
    ci_status = combined_status.state if has_statuses else ""
    if not ci_status:
        if any(c.conclusion in ("failure", "timed_out", "action_required") for c in check_runs):
            ci_status = "failure"
        elif any(c.status != "completed" for c in check_runs):
            ci_status = "pending"
        elif check_runs:
            ci_status = "success"

    ahead = behind = changed_files = 0
    if open_prs:
        newest_pr = max(open_prs, key=lambda pr: pr.created_at)
        changed_files = newest_pr.changed_files
        try:
            comparison = repo.compare(newest_pr.base.ref, newest_pr.head.ref)
            ahead = comparison.ahead_by
            behind = comparison.behind_by
        except github.GithubException:
            pass

    return {
        "branch": default_branch,
        "ahead": ahead,
        "behind": behind,
        "open_prs": len(open_prs),
        "ci_status": ci_status,
        "last_commit": last_commit,
        "changed_files": changed_files,
        "checks": checks,
        "coverage_pct": coverage_pct,
    }
