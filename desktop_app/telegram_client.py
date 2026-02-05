import logging
import requests


class TelegramClient:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    def send_message(self, chat_id: str, text: str) -> tuple[bool, str]:
        if not self.bot_token:
            return False, "Missing bot token"
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                data={"chat_id": chat_id, "text": text},
                timeout=10,
            )
            if response.status_code != 200:
                logging.error("Telegram send failed: %s", response.text)
                return False, response.text
            return True, "OK"
        except requests.RequestException as exc:
            logging.error("Telegram send exception: %s", exc)
            return False, str(exc)
