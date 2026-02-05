import requests


def send_message(bot_token: str, chat_id: str, text: str) -> tuple[bool, str | None]:
    if not bot_token:
        return False, "BOT_TOKEN_MISSING"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)
    except requests.RequestException as exc:
        return False, str(exc)
    if response.status_code != 200:
        return False, f"HTTP_{response.status_code}"
    payload = response.json()
    if not payload.get("ok"):
        return False, payload.get("description", "UNKNOWN_ERROR")
    return True, None
