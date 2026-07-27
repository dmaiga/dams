import logging
import os

import requests

logger = logging.getLogger("monitoring.telegram")

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramProvider:
    """Diffuse une Alerte sur Telegram (bot @dams_agro_bot, TELEGRAM_BOT_TOKEN/
    TELEGRAM_CHAT_ID en .env). Si les credentials sont absents, se comporte comme
    le stub d'origine : logue l'alerte au lieu de l'envoyer.

    Ne lève jamais d'exception vers l'appelant (US-05) : l'échec d'envoi ne doit
    jamais interrompre le flux métier qui l'a déclenché."""

    @staticmethod
    def send(alerte):
        message = f"[{alerte.get_niveau_display()}] {alerte.message}"

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            logger.info("Telegram (stub) — %s", message)
            return

        try:
            response = requests.post(
                TELEGRAM_API_URL.format(token=token),
                data={"chat_id": chat_id, "text": message},
                timeout=10,
            )
            response.raise_for_status()
        except Exception:
            logger.exception("Échec d'envoi Telegram pour Alerte #%s", alerte.pk)
