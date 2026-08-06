"""Detecção de stack e sugestão de comandos de build/test/lint (RF-01).

Determinístico e barato: lê a raiz do repositório e um punhado de arquivos
de manifesto pela API do GitHub, sem envolver agente nem gastar token. O
resultado é sempre uma *sugestão* — a tela de cadastro deixa o usuário
corrigir tudo antes de salvar.

As funções de análise (`_detect_*`) são puras: recebem os arquivos já lidos
e devolvem o resultado, o que as torna testáveis sem rede.
"""

import json
import logging
import re

from . import github_repos

logger = logging.getLogger(__name__)

# Manifesto -> (rótulo do ecossistema, arquivos extras que valem a leitura).
_MANIFESTS = {
    "package.json": "Node",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "composer.json": "PHP",
    "Gemfile": "Ruby",
    "pubspec.yaml": "Dart",
}

# Dependência -> framework, na ordem em que devem ser testadas (a primeira
# que casar vence, então o mais específico vem antes).
_NODE_FRAMEWORKS = [
    ("next", "Next.js"),
    ("nuxt", "Nuxt"),
    ("@remix-run/react", "Remix"),
    ("astro", "Astro"),
    ("@nestjs/core", "NestJS"),
    ("fastify", "Fastify"),
    ("express", "Express"),
    ("vite", "Vite"),
    ("svelte", "Svelte"),
    ("vue", "Vue"),
    ("react", "React"),
]

_PYTHON_FRAMEWORKS = [
    ("django", "Django"),
    ("fastapi", "FastAPI"),
    ("flask", "Flask"),
    ("scrapy", "Scrapy"),
    ("torch", "PyTorch"),
]

# Lockfile -> gerenciador de pacotes Node.
_NODE_PACKAGE_MANAGERS = [
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
]


# Onde procurar quando a raiz não tem manifesto: monorepos costumam manter o
# código em uma destas pastas (o próprio Gestor de Projetos é assim, com
# `frontend/`). Ordem importa — a primeira que casar vence.
_SUBDIR_CANDIDATES = ["backend", "server", "api", "app", "src", "frontend", "web", "client"]


def detect_stack(owner: str, repo: str) -> dict:
    """Analisa o repositório e devolve stack + comandos sugeridos.

    Procura o manifesto na raiz e, se não achar, um nível abaixo nas pastas
    convencionais de monorepo. Nunca levanta por repositório sem manifesto
    reconhecido — devolve os campos vazios, e a tela pede para o usuário
    preencher.
    """
    root_files = github_repos.list_files(owner, repo)

    if _find_manifest(root_files):
        return _detect_in(owner, repo, root_files, subdir="")

    for subdir in _SUBDIR_CANDIDATES:
        if subdir not in root_files:
            continue
        sub_files = github_repos.list_files(owner, repo, subdir)
        if _find_manifest(sub_files):
            return _detect_in(owner, repo, sub_files, subdir=subdir)

    return _empty_result(root_files)


def _find_manifest(files: list[str]) -> str | None:
    return next((name for name in _MANIFESTS if name in files), None)


def _detect_in(owner: str, repo: str, files: list[str], subdir: str) -> dict:
    """Roda a detecção sobre `files` e, quando eles vêm de uma subpasta,
    prefixa os comandos com `cd <subdir>` — o worktree do agente abre na
    raiz do repositório, então um `pytest` cru não rodaria."""
    prefix = f"{subdir}/" if subdir else ""
    ecosystem = _MANIFESTS[_find_manifest(files)]

    if ecosystem == "Node":
        result = _detect_node(files, github_repos.read_text_file(owner, repo, f"{prefix}package.json"))
    elif ecosystem == "Python":
        result = _detect_python(
            files,
            github_repos.read_text_file(owner, repo, f"{prefix}pyproject.toml"),
            github_repos.read_text_file(owner, repo, f"{prefix}requirements.txt"),
        )
    else:
        result = _detect_simple(ecosystem, files)

    result["subdir"] = subdir
    if subdir:
        for key in ("build_command", "test_command", "lint_command"):
            if result[key]:
                result[key] = f"cd {subdir} && {result[key]}"
    return result


def _empty_result(root_files: list[str]) -> dict:
    return {
        "stack": "",
        "build_command": "",
        "test_command": "",
        "lint_command": "",
        "subdir": "",
        "detected_from": root_files[:20],
    }


def _detect_node(root_files: list[str], package_json: str | None) -> dict:
    result = _empty_result(root_files)
    manager = next((m for lock, m in _NODE_PACKAGE_MANAGERS if lock in root_files), "npm")

    try:
        package = json.loads(package_json or "{}")
    except json.JSONDecodeError:
        logger.warning("stack_detect: package.json inválido, seguindo só pelos arquivos da raiz")
        package = {}

    deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
    framework = next((label for dep, label in _NODE_FRAMEWORKS if dep in deps), "")
    result["stack"] = f"Node · {framework}" if framework else "Node"

    # Só sugere comandos que existem de verdade nos scripts do projeto.
    scripts = package.get("scripts", {})
    run = f"{manager} run" if manager != "npm" else "npm run"
    if "build" in scripts:
        result["build_command"] = f"{run} build"
    if "test" in scripts:
        result["test_command"] = f"{run} test"
    if "lint" in scripts:
        result["lint_command"] = f"{run} lint"
    return result


def _detect_python(root_files: list[str], pyproject: str | None, requirements: str | None) -> dict:
    result = _empty_result(root_files)
    blob = f"{pyproject or ''}\n{requirements or ''}".lower()

    framework = next((label for dep, label in _PYTHON_FRAMEWORKS if dep in blob), "")
    result["stack"] = f"Python · {framework}" if framework else "Python"

    if "uv.lock" in root_files:
        result["build_command"] = "uv sync"
    elif "poetry.lock" in root_files or "[tool.poetry]" in (pyproject or ""):
        result["build_command"] = "poetry install"
    elif "requirements.txt" in root_files:
        result["build_command"] = "pip install -r requirements.txt"

    if "pytest" in blob:
        result["test_command"] = "pytest"
    elif "manage.py" in root_files:
        result["test_command"] = "python manage.py test"

    if "ruff" in blob:
        result["lint_command"] = "ruff check ."
    elif "flake8" in blob:
        result["lint_command"] = "flake8"
    return result


def _detect_simple(ecosystem: str, root_files: list[str]) -> dict:
    """Ecossistemas cujos comandos são convencionais o bastante para não
    precisarem de leitura de manifesto."""
    defaults = {
        "Go": ("go build ./...", "go test ./...", "gofmt -l ."),
        "Rust": ("cargo build", "cargo test", "cargo clippy"),
        "PHP": ("composer install", "vendor/bin/phpunit", ""),
        "Ruby": ("bundle install", "bundle exec rspec", "rubocop"),
        "Dart": ("flutter pub get", "flutter test", "dart analyze"),
    }
    build, test, lint = defaults[ecosystem]
    result = _empty_result(root_files)
    result.update(stack=ecosystem, build_command=build, test_command=test, lint_command=lint)
    return result


# Usado pelo wizard de criação do zero (RF-02) para transformar a escolha de
# stack do usuário nos mesmos campos que a detecção produz.
def suggest_for_stack(stack: str) -> dict:
    """Comandos convencionais para uma stack escolhida à mão."""
    normalized = re.sub(r"\s+", " ", stack).strip()
    for ecosystem in ("Go", "Rust", "PHP", "Ruby", "Dart"):
        if normalized.lower().startswith(ecosystem.lower()):
            return _detect_simple(ecosystem, [])
    if normalized.lower().startswith("python"):
        return {
            "stack": normalized,
            "build_command": "pip install -r requirements.txt",
            "test_command": "pytest",
            "lint_command": "ruff check .",
            "detected_from": [],
        }
    return {
        "stack": normalized,
        "build_command": "npm run build",
        "test_command": "npm test",
        "lint_command": "npm run lint",
        "detected_from": [],
    }
