import hmac
import json
import logging
import os
from datetime import datetime

import requests


def push_to_desktop(chat_id, user_name, text, ts=None, message_id=None):
    port = os.getenv("DESKTOP_LOCAL_PORT", "8765")
    secret = os.getenv("DESKTOP_SHARED_SECRET", "")
    if not secret:
        logging.info("Desktop push skipped: missing DESKTOP_SHARED_SECRET")
        return
    payload = {
        "chat_id": str(chat_id),
        "user_name": user_name,
        "text": text,
        "ts": ts or datetime.utcnow().isoformat(),
        "message_id": str(message_id) if message_id is not None else "",
    }
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, "sha256").hexdigest()
    try:
        requests.post(
            f"http://127.0.0.1:{port}/api/telegram/incoming",
            data=body,
            headers={"Content-Type": "application/json", "X-Signature": signature},
            timeout=2,
        )
    except Exception as exc:
        logging.error("Desktop push failed: %s", exc)
