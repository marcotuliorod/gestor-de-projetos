"""Production settings placeholder.

NÃO usado na Fase 0/1 (desenvolvimento é local via docker-compose).
Deixado como ponto de extensão para a fase de deploy VPS/Tailscale/Caddy.
"""
from .base import *  # noqa: F401,F403

DEBUG = False

# TODO(deploy): endurecer para produção quando a fase de VPS chegar —
# SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE,
# SECURE_HSTS_*, ALLOWED_HOSTS restrito, logging estruturado, etc.
