"""The live page's server: one standard-library process on 127.0.0.1 that serves the page and answers /api/*."""
from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import stats as stats_mod
from ..engine import teams
from ..engine.items import item_name
from ..engine.pretty import move_name
from . import moveflow, scout

HERE = Path(__file__).resolve().parent
ICONS = Path(__file__).resolve().parents[3] / "sources" / "icons"
TYPEICONS = ICONS.parent / "typeicons"
TYPEICON = re.compile(r"^/typeicons/([a-z]+)\.svg$")
SPRITE = re.compile(r"^/sprites/([a-z0-9-]+)\.png$")
MAX_BODY = 1_000_000


def check_specs(team, strict=True):
    """Validate a list of Pokémon specs (from the team file or the page's builder); ValueError says what is wrong."""
    if not isinstance(team, list) or not team or len(team) > 6:
        raise ValueError("a team is 1 to 6 Pokémon")
    mv = teams.moves_data()
    for spec in team:
        if not isinstance(spec, dict):
            raise ValueError("each Pokémon is an object")
        try:
            teams.build_mon(spec)        # fails loudly on an unknown species, nature or Stat Point spread
        except (KeyError, TypeError, AttributeError) as e:
            raise ValueError(f"bad Pokémon spec: {type(e).__name__} {e}") from e
        bad = [m for m in spec.get("moves", []) if teams.key(m) not in mv] if strict else []   # a team file may name moves the data lacks
        if bad or len(spec.get("moves", [])) > 4:
            raise ValueError(f"{spec['species']}: unknown move {bad[0]}" if bad else f"{spec['species']}: at most 4 moves")
    return team


def fill_specs(team):
    """A page-built team may be just names: fill what is missing with the species' usual build (as for their side)."""
    if not isinstance(team, list) or not team or len(team) > 6:
        raise ValueError("a team is 1 to 6 Pokémon")
    out = []
    for spec in team:
        if not isinstance(spec, dict) or not isinstance(spec.get("species"), str):
            raise ValueError("each Pokémon is an object with a species")
        out.append({**scout.foe_spec(spec["species"]), **{k: v for k, v in spec.items() if v not in (None, "", [])}})
    return check_specs(out)


def load_team(path):
    if path is None:
        return []                        # no team file: the page builds the team
    data = json.loads(Path(path).read_text())
    team = data["team"] if isinstance(data, dict) else data
    if not isinstance(team, list) or not team:
        raise ValueError("team file: a non-empty list of Pokémon specs")
    return check_specs(team, strict=False)


def dex():
    sp = scout.species_data()
    items = json.loads((Path(teams.DATA) / "items.json").read_text())["items"]
    return {"species": {n: {"label": move_name(n), "types": s["types"], "abilities": s["abilities"],
                            "mega": s["is_mega"], "learnset": scout.learnsets().get(s["species"], [])}
                        for n, s in sp.items()},
            "moves": {i: {"name": m["name"], "type": m["type"], "category": m["category"], "bp": m["base_power"],
                          "pp": m["pp"], "priority": m["priority"], "target": m["target"], "fx": moveflow.flow(i)}
                      for i, m in teams.moves_data().items()},
            "items": {i: v["name"] for i, v in items.items()}, "natures": sorted(stats_mod._UP_DOWN.keys() | stats_mod.NEUTRAL),
            "status_immune": moveflow.STATUS_IMMUNE}


def make_handler(team_path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, separators=(",", ":")).encode(), "application/json")

        def _error(self, code, msg):
            self._json(code, {"error": msg})

        def do_GET(self):
            path = self.path.split("?")[0]
            try:
                if path in ("/", "/live"):
                    self._send(200, (HERE / "static" / "live.html").read_bytes(), "text/html; charset=utf-8")
                elif path == "/api/dex":
                    self._json(200, dex())
                elif path == "/api/team":
                    self._json(200, {"team": scout.team_view(load_team(team_path))})   # re-read each time
                elif TYPEICON.match(path):
                    f = TYPEICONS / (TYPEICON.match(path).group(1) + ".svg")
                    if not f.exists():
                        return self._error(404, "no such type icon")
                    self._send(200, f.read_bytes(), "image/svg+xml")
                elif SPRITE.match(path):
                    f = ICONS / (SPRITE.match(path).group(1) + ".png")
                    if not f.exists():
                        return self._error(404, "no such sprite")
                    self._send(200, f.read_bytes(), "image/png")
                else:
                    self._error(404, "not found")
            except (OSError, ValueError, KeyError) as e:
                self._error(500, type(e).__name__)

        def do_POST(self):
            if self.path not in ("/api/scout", "/api/team/build"):
                return self._error(404, "not found")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > MAX_BODY:
                    return self._error(400, "body too large")
                try:
                    req = json.loads(self.rfile.read(n) or b"null")
                except ValueError:
                    return self._error(400, "body is not JSON")
                if self.path == "/api/team/build":          # the page's builder: specs in, the team as the page shows it out
                    return self._json(200, {"team": scout.team_view(fill_specs(req.get("specs") if isinstance(req, dict) else None))})
                team = fill_specs(req["team"]) if isinstance(req, dict) and req.get("team") else load_team(team_path)
                if not team:
                    raise scout.BadBoard("no team: pick yours on step 1")
                self._json(200, scout.scout(req, team))
            except scout.BadBoard as e:
                self._error(400, str(e))
            except ValueError as e:
                self._error(400, str(e))
            except (OSError, KeyError) as e:
                self._error(500, type(e).__name__)

    return Handler


def serve(team_path, port=8001):
    load_team(team_path)                 # fail before binding if the team file is bad (None: build the team in the page)
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(team_path))
