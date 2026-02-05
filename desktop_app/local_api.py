import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Callable, Optional
from urllib.parse import urlparse


class LocalApiHandler(BaseHTTPRequestHandler):
    secret: str = ""
    on_message: Optional[Callable[[dict], None]] = None
    logger: logging.Logger

    def _send(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        self.logger.info("LOCAL_API: " + format, *args)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/telegram/incoming":
            self._send(404, {"error": "not_found"})
            return
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        signature = self.headers.get("X-Signature", "")
        expected = hmac.new(self.secret.encode("utf-8"), body, "sha256").hexdigest()
        if not hmac.compare_digest(signature, expected):
            self.logger.error("LOCAL_API_SIGNATURE_INVALID")
            self._send(401, {"error": "invalid_signature"})
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid_json"})
            return
        if self.on_message:
            self.on_message(payload)
        self._send(200, {"status": "ok"})


class LocalApiServer:
    def __init__(self, host: str, port: int, secret: str, logger: logging.Logger) -> None:
        self.host = host
        self.port = port
        self.secret = secret
        self.logger = logger
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[Thread] = None

    def start(self, on_message: Callable[[dict], None]) -> None:
        handler = self._build_handler(on_message)
        self._server = HTTPServer((self.host, self.port), handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self.logger.info("Local API server started on %s:%s", self.host, self.port)

    def _build_handler(self, on_message: Callable[[dict], None]):
        secret = self.secret
        logger = self.logger

        class Handler(LocalApiHandler):
            pass

        Handler.secret = secret
        Handler.on_message = on_message
        Handler.logger = logger
        return Handler

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self.logger.info("Local API server stopped")
