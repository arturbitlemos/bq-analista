from __future__ import annotations

import argparse
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx


CREDS_DEFAULT = Path.home() / ".mcp" / "credentials.json"


def save_credentials(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    os.chmod(path, 0o600)


def _capture_code(port: int, timeout_s: int = 120) -> str:
    code_holder: dict[str, str] = {}
    stop_event = threading.Event()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            qs = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(qs)
            if "code" in params:
                code_holder["code"] = params["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>OK</h1><p>You can close this tab.</p>")
                stop_event.set()
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *args: object) -> None:  # noqa: D401, N802
            return  # silence default logging

    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        if not stop_event.wait(timeout=timeout_s):
            httpd.shutdown()
            raise TimeoutError("OAuth callback not received")
        httpd.shutdown()
    return code_holder["code"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="mcp-login")
    parser.add_argument("--server", default=os.environ.get("MCP_SERVER_URL", "https://mcp-azzas.azzas.com.br"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--creds-path", type=Path, default=CREDS_DEFAULT)
    args = parser.parse_args()

    start_url = f"{args.server}/auth/start"
    print(f"Opening browser to {start_url}")
    webbrowser.open(start_url)
    try:
        code = _capture_code(port=args.port)
    except TimeoutError:
        print("timeout waiting for browser callback", file=sys.stderr)
        sys.exit(1)

    r = httpx.get(f"{args.server}/auth/callback", params={"code": code}, timeout=30)
    if r.status_code != 200:
        print(f"auth failed: {r.status_code} {r.text}", file=sys.stderr)
        sys.exit(2)
    save_credentials(args.creds_path, r.json())
    print(f"credentials saved to {args.creds_path}")
