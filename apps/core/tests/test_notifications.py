from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.notifications import send_telegram_message


class SendTelegramMessageTests(TestCase):
    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
    @patch("apps.core.notifications.requests.post")
    def test_noop_when_not_configured(self, mock_post):
        send_telegram_message("olá")
        mock_post.assert_not_called()

    @override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_CHAT_ID="")
    @patch("apps.core.notifications.requests.post")
    def test_noop_when_only_token_configured(self, mock_post):
        send_telegram_message("olá")
        mock_post.assert_not_called()

    @override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_CHAT_ID="999")
    @patch("apps.core.notifications.requests.post")
    def test_posts_to_telegram_api_when_configured(self, mock_post):
        send_telegram_message("olá mundo")

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://api.telegram.org/bot123:abc/sendMessage")
        self.assertEqual(kwargs["json"], {"chat_id": "999", "text": "olá mundo"})

    @override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_CHAT_ID="999")
    @patch("apps.core.notifications.requests.post", side_effect=Exception("boom"))
    def test_swallows_exceptions(self, mock_post):
        send_telegram_message("olá")  # não deve levantar
