import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


class LocalAPIHandler(BaseHTTPRequestHandler):
    server_version = "StoDesktopLocalAPI/1.0"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/telegram/incoming":
            self._send_json(404, {"error": "not_found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        signature = self.headers.get("X-Signature", "")
        secret = self.server.shared_secret.encode("utf-8")
        expected = hmac.new(secret, raw_body, "sha256").hexdigest()

        if not hmac.compare_digest(signature, expected):
            logging.error("LOCAL_API_SIGNATURE_INVALID")
            self._send_json(401, {"error": "invalid_signature"})
            return

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})
            return

        self.server.on_message(payload)
        self._send_json(200, {"status": "ok"})

    def log_message(self, format, *args):
        logging.info("Local API - %s", format % args)


class LocalAPIServer(Thread):
    def __init__(self, host, port, shared_secret, on_message):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.shared_secret = shared_secret
        self.on_message = on_message
        self.httpd = None

    def run(self):
        self.httpd = ThreadingHTTPServer((self.host, self.port), LocalAPIHandler)
        self.httpd.shared_secret = self.shared_secret
        self.httpd.on_message = self.on_message
        logging.info("Local API server listening on %s:%s", self.host, self.port)
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
