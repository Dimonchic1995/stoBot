import hmac
import json
import logging
import os
from datetime import datetime

import requests


def push_to_desktop(chat_id: str, user_name: str, text: str, ts: str, message_id: str) -> None:
    secret = os.getenv("DESKTOP_SHARED_SECRET", "")
    if not secret:
        logging.warning("Desktop shared secret missing")
        return
    port = os.getenv("DESKTOP_API_PORT", "8765")
    url = f"http://127.0.0.1:{port}/api/telegram/incoming"
    payload = {
        "chat_id": chat_id,
        "user_name": user_name,
        "text": text,
        "ts": ts,
        "message_id": message_id,
    }
    body = json.dumps(payload, ensure_ascii=False)
    signature = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), "sha256").hexdigest()
    try:
        response = requests.post(
            url,
            data=body.encode("utf-8"),
            headers={"X-Signature": signature, "Content-Type": "application/json"},
            timeout=3,
        )
        if response.status_code != 200:
            logging.error("Desktop push failed: %s", response.status_code)
    except requests.RequestException as exc:
        logging.error("Desktop push error: %s", exc)


def push_summary(chat_id: str, user_name: str, summary: str, message_id: str) -> None:
    ts = datetime.utcnow().isoformat()
    push_to_desktop(chat_id, user_name, summary, ts, message_id)
