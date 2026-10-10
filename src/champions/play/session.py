"""One game as `(config, action history)`. The Battle is rebuilt from the seed on every change, so undo and restart
are just a shorter history. Anything that goes wrong with user input surfaces as ValueError."""
import random
from dataclasses import asdict

from ..battle import Battle

SIDES = ("p1", "p2")


def _guard(fn):
    """Run engine code, turning the odd lookup failure (unknown species, missing key, wrong JSON type) into ValueError."""
    try:
        return fn()
    except ValueError:
        raise
    except KeyError as e:
        raise ValueError(f"unknown or missing: {e.args[0]}") from None
    except (TypeError, AttributeError) as e:
        raise ValueError(f"malformed input ({e})") from None
    except SystemExit as e:
        raise ValueError(str(e.code)) from None


def _clean_config(raw):
    if not isinstance(raw, dict):
        raise ValueError("expected a JSON object with 'teams'")
    teams = raw.get("teams")
    if not isinstance(teams, dict) or set(teams) != set(SIDES):
        raise ValueError("'teams' must have exactly p1 and p2")
    for side, team in teams.items():
        if not isinstance(team, list) or not team or not all(isinstance(s, dict) for s in team):
            raise ValueError(f"{side} needs a non-empty list of Pokémon objects")
    active = raw.get("active", 1)
    if active not in (1, 2) or isinstance(active, bool):
        raise ValueError("'active' must be 1 or 2")
    seed = raw.get("seed", random.randrange(2 ** 31))
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("'seed' must be an integer")
    field = raw.get("field")
    if field is not None and not isinstance(field, dict):
        raise ValueError("'field' must be an object")
    return {"teams": teams, "active": active, "seed": seed, "field": field}


class Session:
    def __init__(self):
        self.config = None
        self.history = []  # {"turn": actions} or {"replace": {slot: team_index}}
        self.battle = None
        self._last = None  # the latest TurnResult, for its frames

    # -- building ------------------------------------------------------------------------------------------
    @staticmethod
    def _build(config):
        return Battle(config["teams"], active=config["active"], field=config["field"], seed=config["seed"])

    @staticmethod
    def _apply(battle, entry):
        if "turn" in entry:
            return battle.turn(entry["turn"])
        for slot, idx in entry["replace"].items():
            battle.replace(slot, idx)
        return None

    def _require(self):
        if self.config is None:
            raise ValueError("no game in progress; POST /api/new first")

    def _rebuild(self, history):
        battle, last = self._build(self.config), None
        for entry in history:
            last = self._apply(battle, entry) or last
        return battle, last

    # -- commands ------------------------------------------------------------------------------------------
    def new(self, raw):
        config = _clean_config(raw)
        battle = _guard(lambda: self._build(config))  # a bad team must not replace the running game
        self.config, self.history, self.battle, self._last = config, [], battle, None
        return self.view()

    def turn(self, actions):
        self._require()
        if not isinstance(actions, dict) or not all(isinstance(a, dict) for a in actions.values()):
            raise ValueError("'actions' must map each slot to an action object")
        return self._record({"turn": actions})

    def replace(self, replacements):
        self._require()
        if not isinstance(replacements, dict) or not replacements:
            raise ValueError("'replacements' must map slots to team indexes")
        return self._record({"replace": replacements})

    def _record(self, entry):
        # Play the entry on a fresh replay so a rejected action leaves the live battle untouched.
        battle, _ = _guard(lambda: self._rebuild(self.history))
        result = _guard(lambda: self._apply(battle, entry))
        self.battle, self._last = battle, result
        self.history.append(entry)
        return self.view()

    def undo(self):
        self._require()
        if not self.history:
            raise ValueError("nothing to undo")
        self.history.pop()
        self.battle, self._last = self._rebuild(self.history)
        self._last = None
        return self.view()

    def restart(self):
        self._require()
        self.history = []
        self.battle, self._last = self._build(self.config), None
        return self.view()

    # -- what the browser renders --------------------------------------------------------------------------
    def view(self):
        if self.config is None:
            return {"started": False}
        b = self.battle
        out = {"started": True, "snapshot": b.snapshot(), "pending": b.pending_replacements(), "winner": b.winner,
               "legal": {slot: b.legal_actions(slot) for slot in b.slots}, "history": len(self.history),
               "config": self.config}
        if self._last is not None:
            out.update({k: v for k, v in asdict(self._last).items() if k != "pending"})
        return out
