import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from typing import Optional

import requests


DESKTOP_PORT = int(os.getenv("DESKTOP_LOCAL_API_PORT", "8765"))
DESKTOP_SECRET = os.getenv("DESKTOP_SHARED_SECRET", "")


def _signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def push_incoming(
    chat_id: str,
    user_name: str,
    text: str,
    ts: Optional[str] = None,
    message_id: Optional[str] = None,
) -> None:
    if not DESKTOP_SECRET:
        logging.warning("Desktop shared secret not configured")
        return
    payload = {
        "chat_id": chat_id,
        "user_name": user_name,
        "text": text,
        "ts": ts or datetime.utcnow().isoformat(),
        "message_id": message_id or "",
    }
    raw = json.dumps(payload).encode("utf-8")
    signature = _signature(DESKTOP_SECRET, raw)
    try:
        requests.post(
            f"http://127.0.0.1:{DESKTOP_PORT}/api/telegram/incoming",
            data=raw,
            headers={"X-Signature": signature, "Content-Type": "application/json"},
            timeout=3,
        )
    except requests.RequestException as exc:
        logging.warning("Desktop push failed: %s", exc)
