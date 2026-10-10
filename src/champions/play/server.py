"""Stdlib JSON API plus the single-page UI. The browser holds no game logic: it posts actions and renders views.

GET  /               the page
GET  /icons/<type>.png  type icon (one of the 18 types)
GET  /api/dex        species, supported moves, items, natures
GET  /api/state      current view (or {"started": false})
POST /api/new        {teams: {p1: [...], p2: [...]}, active: 1|2, seed?, field?}
POST /api/turn       {actions: {slot: {move, target} | {switch}}}
POST /api/replace    {replacements: {slot: team_index}}
POST /api/undo, /api/restart
Every error is `{"error": text}` with HTTP 400 (404 for unknown routes), never a traceback.
"""
import argparse
import json
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..battle.dex import dex
from .session import Session

STATIC = Path(__file__).parent / "static"
PAGE = STATIC / "index.html"
ICON_ROUTE = re.compile(r"/icons/([a-z]+)\.png")
MAX_BODY = 1_000_000


class Handler(BaseHTTPRequestHandler):
    server_version = "champions-play"

    def log_message(self, fmt, *args):  # keep the terminal quiet
        pass

    # -- plumbing ------------------------------------------------------------------------------------------
    def _send(self, status, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ValueError("bad Content-Length") from None
        if length > MAX_BODY:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except (ValueError, UnicodeDecodeError):
            raise ValueError("body is not valid JSON") from None
        if not isinstance(body, dict):
            raise ValueError("body must be a JSON object")
        return body

    def _dispatch(self, routes):
        path = self.path.split("?", 1)[0]
        handler = routes.get(path)
        if handler is None:
            return self._send(404, {"error": f"not found: {path}"})
        try:
            result = handler(self)
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:  # last resort: report it, keep serving
            return self._send(500, {"error": f"internal error: {type(e).__name__}"})
        if isinstance(result, tuple):
            return self._send(200, result[0], result[1])
        self._send(200, result)

    # -- routes --------------------------------------------------------------------------------------------
    def _locked(self, fn):
        with self.server.lock:
            return fn(self.server.session)

    GET = {
        "/": lambda h: (PAGE.read_bytes(), "text/html; charset=utf-8"),
        "/api/dex": lambda h: dex(),
        "/api/state": lambda h: h._locked(lambda s: s.view()),
    }
    POST = {
        "/api/new": lambda h: h._locked(lambda s: s.new(h._read_json())),
        "/api/turn": lambda h: h._locked(lambda s: s.turn(h._read_json().get("actions"))),
        "/api/replace": lambda h: h._locked(lambda s: s.replace(h._read_json().get("replacements"))),
        "/api/undo": lambda h: h._locked(lambda s: s.undo()),
        "/api/restart": lambda h: h._locked(lambda s: s.restart()),
    }

    def do_GET(self):
        icon = ICON_ROUTE.fullmatch(self.path.split("?", 1)[0])
        if icon and (STATIC / "icons" / f"{icon[1]}.png").is_file():  # the regex keeps the name to letters only
            return self._send(200, (STATIC / "icons" / f"{icon[1]}.png").read_bytes(), "image/png")
        self._dispatch(self.GET)

    def do_POST(self):
        self._dispatch(self.POST)


def make_server(port=8000, host="127.0.0.1"):
    server = ThreadingHTTPServer((host, port), Handler)
    server.session, server.lock = Session(), threading.Lock()
    return server


def main():
    ap = argparse.ArgumentParser(prog="champions play", description="Play a Champions doubles battle in the browser.")
    ap.add_argument("--port", type=int, default=8000, help="port to listen on (0 = any free port; default 8000)")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser tab")
    args = ap.parse_args()
    server = make_server(args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"champions play: {url}  (Ctrl-C to stop)")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
