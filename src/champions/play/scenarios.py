"""Battle tests as playable scenarios. Runs the classes in `tests/test_battle_cases.py` with `Battle` wrapped to
record its setup and every turn/replace, so the browser can load a test and step through exactly what it does.
Needs a source checkout (the tests are not part of the installed package)."""
import copy
import inspect
import sys
import unittest
from pathlib import Path

from ..battle import Battle

ROOT = Path(__file__).resolve().parents[3]
MODULE = "tests.test_battle_cases"


class _Recorder(Battle):
    """A Battle that logs how it was built and what was played on it."""
    log = None  # the list the current test's recording goes into

    def __init__(self, teams, **kw):
        super().__init__(teams, **kw)
        self.recording = {"teams": copy.deepcopy(teams), "history": []}
        self.recording.update({k: copy.deepcopy(kw[k]) for k in ("active", "field", "chance", "rolls") if k in kw})
        self.recording["seed"] = kw.get("seed", 0)  # the session would otherwise pick a random one
        if _Recorder.log is not None:
            _Recorder.log.append(self)

    def turn(self, actions):
        out = super().turn(actions)
        self.recording["history"].append({"turn": copy.deepcopy(actions)})
        return out

    def replace(self, slot, team_index):
        out = super().replace(slot, team_index)
        self.recording["history"].append({"replace": {slot: team_index}})
        return out


def _load_module():
    if not (ROOT / "tests" / "test_battle_cases.py").is_file():
        raise ValueError("battle scenarios need a source checkout (tests/test_battle_cases.py not found)")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import importlib
    return importlib.import_module(MODULE)


def collect():
    """[{id, group, name, source, config, history, battle, error}] for every battle test that builds a Battle.
    `battle` is the test's own final Battle (for comparing against a play-session replay); not JSON-safe."""
    mod = _load_module()
    mod_battle, mod.Battle = mod.Battle, _Recorder  # the test module imported the name directly
    out = []
    try:
        for cls_name, cls in sorted(vars(mod).items()):
            if not (inspect.isclass(cls) and issubclass(cls, unittest.TestCase) and cls.__module__ == mod.__name__):
                continue
            for name in sorted(n for n in dir(cls) if n.startswith("test_")):
                _Recorder.log = []
                error = None
                try:
                    getattr(cls(name), name)()
                except Exception as e:  # a failing test is still worth loading, to see why
                    error = f"{type(e).__name__}: {e}"
                battles, _Recorder.log = _Recorder.log, None
                if not battles:
                    continue
                b = battles[0]  # tests that build many (seed sweeps) are shown by their first
                rec = b.recording
                config = {k: v for k, v in rec.items() if k != "history"}
                doc = inspect.getdoc(cls) or ""
                out.append({"id": f"{cls_name}.{name}", "group": cls_name, "name": name[5:].replace("_", " "),
                            "source": doc, "config": config, "history": rec["history"], "battle": b, "error": error})
    finally:
        mod.Battle = mod_battle
    return out
