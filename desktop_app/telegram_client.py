import logging
from typing import Tuple

import requests


class TelegramClient:
    def __init__(self, bot_token: str, logger: logging.Logger) -> None:
        self.bot_token = bot_token
        self.logger = logger

    def send_message(self, chat_id: str, text: str) -> Tuple[bool, str]:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
        except requests.RequestException as exc:
            self.logger.error("Telegram send failed: %s", exc)
            return False, str(exc)
        if response.status_code != 200:
            self.logger.error("Telegram send failed: %s", response.text)
            return False, response.text
        return True, "ok"

    def test(self) -> Tuple[bool, str]:
        url = f"https://api.telegram.org/bot{self.bot_token}/getMe"
        try:
            response = requests.get(url, timeout=10)
        except requests.RequestException as exc:
            return False, str(exc)
        if response.status_code != 200:
            return False, response.text
        return True, "ok"
