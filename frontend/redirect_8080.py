#!/usr/bin/env python3
"""Redirect http://localhost:8080 → http://localhost:5000 (legacy port)."""
from http.server import BaseHTTPRequestHandler, HTTPServer

import os

# Use localhost so the host browser hits forwarded ports, not container-only 127.0.0.1
TARGET = os.environ.get("PUBLIC_UI_URL", "http://localhost:5000")


class RedirectHandler(BaseHTTPRequestHandler):
    def _redirect(self):
        path = self.path if self.path.startswith("/") else "/" + self.path
        location = TARGET + path
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def do_GET(self):
        self._redirect()

    def do_POST(self):
        self._redirect()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    print(f"Redirecting :8080 → {TARGET}")
    HTTPServer(("0.0.0.0", 8080), RedirectHandler).serve_forever()
