import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Callable

from PySide6.QtCore import QObject, Signal


class LocalApiServer(QObject):
    message_received = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def start(self, port: int, shared_secret: str) -> None:
        if self._server:
            self.stop()

        handler = self._build_handler(shared_secret)
        self._server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logging.info("Local API listening on %s", port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None

    def _build_handler(self, shared_secret: str):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/api/telegram/incoming":
                    self.send_response(404)
                    self.end_headers()
                    return

                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length)
                signature = self.headers.get("X-Signature", "")
                expected = hmac.new(
                    shared_secret.encode("utf-8"), body, "sha256"
                ).hexdigest()

                if not hmac.compare_digest(signature, expected):
                    logging.error("LOCAL_API_SIGNATURE_INVALID")
                    self.send_response(401)
                    self.end_headers()
                    return

                try:
                    payload = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.end_headers()
                    return

                parent.message_received.emit(payload)
                self.send_response(200)
                self.end_headers()

            def log_message(self, format, *args):
                return

        return Handler
