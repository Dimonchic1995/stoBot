import hashlib
import hmac
import json
import logging
import os
from datetime import datetime

import requests


def send_incoming_message(chat_id: str, user_name: str, text: str, message_id: str) -> None:
    shared_secret = os.getenv("DESKTOP_SHARED_SECRET", "")
    port = os.getenv("DESKTOP_API_PORT", "8765")
    if not shared_secret:
        logging.warning("DESKTOP_SHARED_SECRET missing")
        return

    payload = {
        "chat_id": chat_id,
        "user_name": user_name,
        "text": text,
        "ts": datetime.utcnow().isoformat(),
        "message_id": message_id,
    }
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(shared_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    url = f"http://127.0.0.1:{port}/api/telegram/incoming"
    try:
        requests.post(url, data=body, headers={"X-Signature": signature}, timeout=3)
    except requests.RequestException as exc:
        logging.warning("Desktop push failed: %s", exc)
