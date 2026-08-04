"""Development settings."""
from .base import *  # noqa: F401,F403

DEBUG = True

# Permissive by default for local docker-compose; overridden by env if set.
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "0.0.0.0"]  # noqa: F405
