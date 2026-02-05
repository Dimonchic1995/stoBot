import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Callable
from urllib.parse import urlparse


class IncomingRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/telegram/incoming":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        signature = self.headers.get("X-Signature", "")
        if not self.server.verify_signature(raw_body, signature):
            logging.error("LOCAL_API_SIGNATURE_INVALID")
            self.send_response(401)
            self.end_headers()
            return

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        self.server.handle_payload(payload)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


class LocalAPIServer:
    def __init__(self, host: str, port: int, shared_secret: str, on_message: Callable[[dict], None]):
        self.host = host
        self.port = port
        self.shared_secret = shared_secret.encode("utf-8")
        self.on_message = on_message
        self.httpd: HTTPServer | None = None
        self.thread: Thread | None = None

    def verify_signature(self, body: bytes, signature: str) -> bool:
        expected = hmac.new(self.shared_secret, body, "sha256").hexdigest()
        return hmac.compare_digest(expected, signature)

    def handle_payload(self, payload: dict) -> None:
        self.on_message(payload)

    def start(self) -> None:
        if self.httpd:
            return

        server = HTTPServer((self.host, self.port), IncomingRequestHandler)
        server.verify_signature = self.verify_signature
        server.handle_payload = self.handle_payload
        self.httpd = server
        self.thread = Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        logging.info("Local API server started on %s:%s", self.host, self.port)

    def stop(self) -> None:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.thread:
            self.thread.join(timeout=1)
            self.thread = None
