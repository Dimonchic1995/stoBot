import logging
import requests


def send_message(bot_token: str, chat_id: str, text: str):
    if not bot_token:
        raise ValueError("BOT_TOKEN missing")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": text})
    if not response.ok:
        logging.error("Telegram send failed: %s", response.text)
        return False, response.text
    return True, response.text


def test_token(bot_token: str):
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    response = requests.get(url)
    if not response.ok:
        return False, response.text
    return True, response.text
