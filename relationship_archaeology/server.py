from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .service import analyse, markdown_export, preview


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
SAMPLE = ROOT / "sample_data" / "demo_chat.txt"
REPLAY = ROOT / "output" / "live_smoke.json"


class Handler(BaseHTTPRequestHandler):
    server_version = "RelationshipArchaeology/0.1"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/sample":
            self._json({"text": SAMPLE.read_text(encoding="utf-8")})
            return
        if path == "/api/health":
            self._json({"ok": True})
            return
        if path == "/api/replay" and os.getenv("ENABLE_REPLAY", "") == "1":
            if not REPLAY.is_file():
                self._json({"error": "尚无可回放的实测结果。"}, status=404)
            else:
                self._json(json.loads(REPLAY.read_text(encoding="utf-8")))
            return
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (STATIC / relative).resolve()
        if STATIC.resolve() not in target.parents and target != STATIC.resolve():
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 30 * 1024 * 1024:
                raise ValueError("上传内容超过 30MB 演示限制。")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/preview":
                self._json(preview(payload))
            elif path == "/api/analyze":
                self._json(analyse(payload))
            elif path == "/api/export":
                result = analyse(payload)
                self._text(markdown_export(result), "text/markdown; charset=utf-8")
            else:
                self.send_error(404)
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, status=400)
        except Exception as exc:  # keep the local demo inspectable
            self._json({"error": str(exc)}, status=500)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[server] {self.address_string()} - {fmt % args}")

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", 'attachment; filename="relationship-yearbook.md"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run() -> None:
    parser = argparse.ArgumentParser(description="Run the Relationship Archaeology demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Enable local replay of output/live_smoke.json for screenshots.",
    )
    args = parser.parse_args()
    if args.replay:
        os.environ["ENABLE_REPLAY"] = "1"
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Relationship Archaeology is running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
