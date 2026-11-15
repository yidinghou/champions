"""Run one catalogue case: build the battle, play the scripted turns, evaluate every check."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..engine import game
from ..engine.actions import from_dict
from ..engine.rng import LabeledRng


@dataclass
class Result:
    owner: dict
    case: dict
    failures: List[str] = field(default_factory=list)
    log: List[str] = field(default_factory=list)

    @property
    def passed(self):
        return not self.failures


def find_mon(battle, ref):
    for side in battle.sides:
        for m in side.team:
            if m.ref == ref:
                return m
    raise KeyError(f"no mon {ref!r}; refs are {[m.ref for s in battle.sides for m in s.team]}")


def _match(event, where):
    return all(event.data.get(k) == v for k, v in (where or {}).items())


def _events(battle, kind, where):
    return [e for e in battle.log if e.kind == kind and _match(e, where)]


def evaluate(battle, chk):
    """Return None if the check holds, else a message with the actual value."""
    if "stage" in chk:
        actual = find_mon(battle, chk["mon"]).stages[chk["stage"]]
        if actual != chk["eq"]:
            return f"stage {chk['stage']} of {chk['mon']} == {chk['eq']}  (actual: {actual})"
    elif "hp" in chk:
        m = find_mon(battle, chk["mon"])
        state = "fainted" if m.fainted else "full" if m.hp == m.max_hp else "damaged"
        if state != chk["hp"]:
            return f"hp of {chk['mon']} is {chk['hp']}  (actual: {state}, {m.hp}/{m.max_hp})"
    elif "hp_eq" in chk:
        m = find_mon(battle, chk["mon"])
        if m.hp != chk["hp_eq"]:
            return f"hp of {chk['mon']} == {chk['hp_eq']}  (actual: {m.hp})"
    elif "status" in chk:
        actual = find_mon(battle, chk["mon"]).status
        if actual != chk["status"]:
            return f"status of {chk['mon']} == {chk['status']}  (actual: {actual})"
    elif "status_turns" in chk:
        actual = find_mon(battle, chk["mon"]).status_turns
        if actual != chk["status_turns"]:
            return f"status_turns of {chk['mon']} == {chk['status_turns']}  (actual: {actual})"
    elif "damage_seq" in chk:     # end-of-turn hits taken, in order, as [n, d] of max HP
        m = find_mon(battle, chk["mon"])
        got = [e.data["amount"] for e in battle.log if e.kind == "damage" and e.data["mon"] == m.ref]
        want = [max(1, m.max_hp // d) * n for n, d in chk["damage_seq"]]   # Showdown floors max/d first, then multiplies
        if got != want:
            return f"damage taken by {chk['mon']} == {want} ({chk['damage_seq']} of {m.max_hp})  (actual: {got})"
    elif "pp_full" in chk:        # the move was never spent
        from ..engine.teams import moves_data
        m = find_mon(battle, chk["mon"])
        want = moves_data()[chk["pp_full"]]["pp"]
        if m.pp[chk["pp_full"]] != want:
            return f"pp of {chk['pp_full']} on {chk['mon']} == {want}  (actual: {m.pp[chk['pp_full']]})"
    elif "arena" in chk:          # field state: weather, weather_turns, terrain, terrain_turns, trick_room (null = absent)
        actual = battle.arena.get(chk["arena"])
        if actual != chk["eq"]:
            return f"arena {chk['arena']} == {chk['eq']}  (actual: {actual})"
    elif "volatile" in chk:
        vols = find_mon(battle, chk["mon"]).volatiles
        present = chk["volatile"] in vols
        if present != chk.get("present", True):
            return f"volatile {chk['volatile']} on {chk['mon']} present={chk.get('present', True)}  (actual: {present})"
        if "eq" in chk and present:       # compare the value, or one key of it ("key")
            actual = vols[chk["volatile"]]
            if "key" in chk:
                actual = actual[chk["key"]]
            if actual != chk["eq"]:
                return f"volatile {chk['volatile']}{'.' + chk['key'] if 'key' in chk else ''} on {chk['mon']} == {chk['eq']}  (actual: {actual})"
    elif "event" in chk:
        n = len(_events(battle, chk["event"], chk.get("where")))
        want = chk.get("count")
        if (want is not None and n != want) or (want is None and n < chk.get("min", 1)):
            return f"event {chk['event']} {chk.get('where') or ''} count {want if want is not None else '>= ' + str(chk.get('min', 1))}  (actual: {n})"
    elif "no_event" in chk:
        n = len(_events(battle, chk["no_event"], chk.get("where")))
        if n:
            return f"no {chk['no_event']} event {chk.get('where') or ''}  (actual: {n} found)"
    elif "recoil" in chk or "heal" in chk:
        who, kind = (chk["recoil"], "recoil") if "recoil" in chk else (chk["heal"], "heal")
        dealt = sum(e.data["amount"] for e in battle.log if e.kind == "damage" and e.data["mon"] == chk["of_damage_to"])
        got = sum(e.data["amount"] for e in battle.log if e.kind == kind and e.data["mon"] == who)
        want = max(1, dealt * chk["n"] // chk["d"]) if dealt else 0
        if got != want:
            return f"{kind} of {who} == {chk['n']}/{chk['d']} of {dealt} damage dealt to {chk['of_damage_to']} = {want}  (actual: {got})"
    elif "order" in chk:
        i = 0
        for e in battle.log:
            kind, where = chk["order"][i]
            if e.kind == kind and _match(e, where):
                i += 1
                if i == len(chk["order"]):
                    return None
        return f"events in order {chk['order']}  (stopped at step {i + 1})"
    else:
        return f"unknown check {chk}"
    return None


def run_case(owner, case):
    res = Result(owner, case)
    run = case["run"]
    battle = None
    try:
        battle = game.start(run["teams"], seed=run.get("seed", 1), format=run.get("format", "doubles"),
                            rng=LabeledRng(run.get("rolls")))
        for ref, stages in run.get("stages", {}).items():      # start-of-case stage setup
            find_mon(battle, ref).stages.update(stages)
        battle.arena.update(run.get("arena", {}))              # e.g. {"trick_room": 4}
        for turn in run.get("turns", []):
            if isinstance(turn, dict):        # {"expect_error": "text", "choices": [...]}: the choice must be refused
                try:
                    game.play_turn(battle, [from_dict(c) for c in turn["choices"]])
                    res.failures.append(f"expected the choices to be refused with {turn['expect_error']!r}, but they were accepted")
                except ValueError as e:
                    if turn["expect_error"] not in str(e):
                        res.failures.append(f"expected a refusal containing {turn['expect_error']!r}  (actual: {e})")
                continue
            game.play_turn(battle, [from_dict(c) for c in turn])
    except Exception as e:  # noqa: BLE001 - report any engine error as the case's failure
        res.failures.append(f"raised {type(e).__name__}: {e}")
    if not run.get("check"):
        res.failures.append("case has no checks, so it proves nothing")
    if battle is not None:
        res.log = [str(e) for e in battle.log]
        for chk in run.get("check", []):
            try:
                msg = evaluate(battle, chk)
            except (KeyError, IndexError) as e:        # a bad check is a failing case, not a crash
                msg = f"could not evaluate {chk}: {e}"
            if msg:
                res.failures.append(msg)
    return res


def run_all(pairs):
    """Run (owner, case) pairs; return the Results in order."""
    return [run_case(o, c) for o, c in pairs]


def upstream_failing(owner, results, mechanics):
    """Ids of mechanics this owner depends on (directly or through the chain) that have failing cases."""
    failing = {r.owner["id"] for r in results if not r.passed}
    deps = {m["id"]: m.get("depends_on", []) for m in mechanics}
    seen, todo = set(), list(owner.get("depends_on", []))
    while todo:
        d = todo.pop()
        if d not in seen:
            seen.add(d)
            todo += deps.get(d, [])
    return sorted(seen & failing)


def format_failure(res, upstream=()):
    o, c = res.owner, res.case
    lines = [f"{o['id']}::{c['id']}  [{c['kind']}, status={c['status']}]",
             f"  setup:   {c['setup']}", f"  expect:  {c['expect']}"]
    src = c.get("source") or (o.get("source") or [None])[0]
    if src:
        lines.append(f"  source:  {src}")
    lines.append("")
    lines += [f"  FAILED check: {f}" for f in res.failures]
    if upstream:
        lines += ["", f"  note: upstream mechanics also have failing cases: {', '.join(upstream)}; fix those first"]
    if res.log:
        lines += ["", "  event log:"] + [f"    {ln}" for ln in res.log]
    return "\n".join(lines)
