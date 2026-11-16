"""champions live [--team FILE] [--port 8001] [--no-open]   serve the live-game tracker on 127.0.0.1."""
import argparse
import sys
import webbrowser

from .server import serve


def main():
    p = argparse.ArgumentParser(prog="champions live")
    p.add_argument("--team", help="your team: a JSON list of specs (see teams/sample.json); without it you pick yours in the page")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--no-open", action="store_true")
    a = p.parse_args()
    try:
        srv = serve(a.team, a.port)
    except (OSError, ValueError, KeyError) as e:
        sys.exit(f"error: {e}")
    url = f"http://127.0.0.1:{a.port}/"
    print(f"live tracker at {url}  (Ctrl-C to stop)")
    if not a.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
