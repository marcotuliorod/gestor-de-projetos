"""Base settings shared across environments."""
from pathlib import Path

import environ

# config/settings/base.py -> project root is three parents up.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

# Read .env if present (docker-compose also injects these via env_file).
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_celery_beat",
    "django_celery_results",
    # Local
    "apps.core",
    "apps.projects",
    "apps.status",
    "apps.agents",
    "apps.budget",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://gestor:gestor@localhost:5432/gestor",
    ),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Celery -------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = "django-db"
CELERY_CACHE_BACKEND = "django-cache"
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_TRACK_STARTED = True
CELERY_TIMEZONE = TIME_ZONE

# --- DRF ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# --- GitHub App (coletor de status real) --------------------------------
GITHUB_APP_ID = env("GITHUB_APP_ID", default="")
GITHUB_APP_PRIVATE_KEY_B64 = env("GITHUB_APP_PRIVATE_KEY_B64", default="")
GITHUB_APP_INSTALLATION_ID = env("GITHUB_APP_INSTALLATION_ID", default="")
GITHUB_WEBHOOK_SECRET = env("GITHUB_WEBHOOK_SECRET", default="")
# Token pessoal usado *exclusivamente* para criar repositório (RF-02).
# Uma GitHub App não consegue criar repositório em conta pessoal: o token
# de instalação não serve para `POST /user/repos`, e a permissão
# `administration` só existe para organizações. Todo o resto do sistema
# continua autenticando pela App.
GITHUB_PAT = env("GITHUB_PAT", default="")

# --- Execução de agentes (RF-07..10, RF-17..20) --------------------------
# Diretório (volume compartilhado web+worker) onde mirrors/worktrees de
# repositório ficam — ver apps/agents/workspace.py.
AGENTS_REPO_ROOT = env("AGENTS_REPO_ROOT", default="/data/repos")
# Credencial do Claude Agent SDK — nome exato a confirmar contra a doc
# oficial no spike de implementação (ver apps/agents/agent_client.py).
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
# Enquanto o spike do SDK não roda, agent_client.run_phase() opera em modo
# determinístico (sem chamar nenhuma API externa) — default True.
AGENTS_FAKE_MODE = env.bool("AGENTS_FAKE_MODE", default=True)

# --- Notificações Telegram (RF-14) ---------------------------------------
# Sem token/chat_id configurados, apps.core.notifications.send_telegram_message
# vira no-op silencioso — mesmo padrão de "degrada graciosamente".
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_CHAT_ID = env("TELEGRAM_CHAT_ID", default="")
