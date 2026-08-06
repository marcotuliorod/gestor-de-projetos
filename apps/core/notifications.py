"""Notificações via Telegram (RF-14) — best-effort, nunca quebra o fluxo
principal (mesmo padrão de `_publish` em apps.agents.tasks)."""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(text: str) -> None:
    """Envia uma mensagem para o chat configurado. No-op silencioso se
    TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID não estiverem configurados. Nunca
    levanta exceção — falha de rede/API só gera um warning no log."""
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return

    try:
        requests.post(
            TELEGRAM_API_URL.format(token=token),
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
    except Exception:
        logger.warning("notifications: falha ao enviar mensagem Telegram (não-fatal)", exc_info=True)
