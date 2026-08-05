"""Gerência de mirrors/worktrees git para execução de agentes (RF-07..10).

Um mirror (bare clone) por projeto é reaproveitado entre TaskRuns; cada
TaskRun ganha um worktree + branch dedicados a partir dele. Autenticação via
token de instalação da GitHub App como credencial HTTPS do git — nunca se
faz push exceto em `push_branch`, chamada só a partir do endpoint /approve/
(RNF-01/RF-10: nunca push/PR sem revisão humana).
"""

import logging
import subprocess
from pathlib import Path

from django.conf import settings

from apps.status.github_client import get_installation_token

logger = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(getattr(settings, "AGENTS_REPO_ROOT", "/data/repos"))


def _mirror_path(project) -> Path:
    return _repo_root() / "mirrors" / f"{project.repo_owner}__{project.repo_name}.git"


def _worktree_path(task_run) -> Path:
    project = task_run.project
    return (
        _repo_root()
        / "worktrees"
        / f"{project.repo_owner}__{project.repo_name}"
        / f"task-{task_run.id}"
    )


def _authenticated_url(project) -> str:
    token = get_installation_token()
    return f"https://x-access-token:{token}@github.com/{project.repo_owner}/{project.repo_name}.git"


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    logger.debug("workspace: %s (cwd=%s)", " ".join(cmd), cwd)
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def ensure_mirror(project) -> Path:
    """Garante um clone bare atualizado do repo em disco, reaproveitado
    entre TaskRuns do mesmo projeto.

    Importante: usamos `--bare` (não `--mirror`). Um clone `--mirror` usa
    o refspec `+refs/*:refs/*`, que trata QUALQUER ref local como se fosse
    do remoto — um `fetch --prune` apagaria os branches dos worktrees de
    TaskRuns ainda não empurrados (ainda não existem no remoto). Com
    `--bare` configuramos o refspec manualmente para só sincronizar
    `refs/remotes/origin/*`, deixando `refs/heads/*` (onde vivem os
    branches dos worktrees) intocado por fetch/prune.
    """
    mirror = _mirror_path(project)
    url = _authenticated_url(project)
    if mirror.exists():
        _run(["git", "remote", "set-url", "origin", url], cwd=mirror)
    else:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", "--bare", url, str(mirror)])
        _run(
            ["git", "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*"],
            cwd=mirror,
        )
    _run(["git", "fetch", "--prune", "origin"], cwd=mirror)
    return mirror


def create_worktree(task_run, base_branch: str) -> Path:
    """Cria um worktree + branch dedicados para este TaskRun a partir do
    branch padrão do projeto (`base_branch`, resolvido via API do GitHub
    antes de chamar esta função — evita reparsear `git remote show`)."""
    project = task_run.project
    mirror = ensure_mirror(project)

    branch = f"agent/task-{task_run.id}"
    worktree_path = _worktree_path(task_run)
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    _run(
        ["git", "worktree", "add", "-b", branch, str(worktree_path), f"origin/{base_branch}"],
        cwd=mirror,
    )
    return worktree_path


def push_branch(task_run) -> None:
    """Push do branch do worktree para origin. Só deve ser chamado pelo
    endpoint /approve/ — nunca automaticamente."""
    project = task_run.project
    mirror = ensure_mirror(project)
    url = _authenticated_url(project)
    _run(["git", "remote", "set-url", "origin", url], cwd=mirror)
    _run(["git", "push", "origin", task_run.branch_name], cwd=mirror)


def discard_worktree(task_run) -> None:
    """Remove o worktree e o branch local. Não toca o remoto — nada foi
    empurrado ainda nesse ponto."""
    project = task_run.project
    mirror = ensure_mirror(project)
    worktree_path = _worktree_path(task_run)
    if worktree_path.exists():
        _run(["git", "worktree", "remove", "--force", str(worktree_path)], cwd=mirror)
    _run(["git", "branch", "-D", task_run.branch_name], cwd=mirror)


def diff_stat(task_run) -> list[dict]:
    """Calcula o diff on-demand a partir do worktree local (nunca
    persistido no banco). Retorna uma lista de
    {path, added, removed, lines: [{type, text}]}."""
    worktree_path = _worktree_path(task_run)
    diff_range = f"{task_run.base_branch}...HEAD"

    numstat = _run(["git", "diff", "--numstat", diff_range], cwd=worktree_path).stdout
    full_diff = _run(["git", "diff", diff_range], cwd=worktree_path).stdout

    stats_by_path = {}
    for line in numstat.splitlines():
        if not line.strip():
            continue
        added, removed, path = line.split("\t")
        stats_by_path[path] = {
            "added": 0 if added == "-" else int(added),
            "removed": 0 if removed == "-" else int(removed),
        }

    return _parse_unified_diff(full_diff, stats_by_path)


def _parse_unified_diff(diff_text: str, stats_by_path: dict) -> list[dict]:
    """Parser simples de `git diff` unificado — path/added/removed/lines.
    Não usa nenhuma dependência nova; cobre o suficiente para a tela de
    Diff (não precisa ser um parser de diff genérico e robusto)."""
    files = []
    current = None

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git "):
            if current is not None:
                files.append(current)
            # "diff --git a/path b/path" — usa a parte depois de "b/".
            b_path = raw_line.split(" b/", 1)[-1]
            stat = stats_by_path.get(b_path, {"added": 0, "removed": 0})
            current = {"path": b_path, "added": stat["added"], "removed": stat["removed"], "lines": []}
            continue
        if current is None:
            continue
        if raw_line.startswith(("index ", "--- ", "+++ ", "new file", "deleted file", "old mode", "new mode")):
            continue
        if raw_line.startswith("@@"):
            current["lines"].append({"type": "context", "text": raw_line})
        elif raw_line.startswith("+"):
            current["lines"].append({"type": "add", "text": raw_line[1:]})
        elif raw_line.startswith("-"):
            current["lines"].append({"type": "del", "text": raw_line[1:]})
        else:
            current["lines"].append({"type": "context", "text": raw_line[1:] if raw_line.startswith(" ") else raw_line})

    if current is not None:
        files.append(current)
    return files
