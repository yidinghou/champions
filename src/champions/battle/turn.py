"""Turn resolution: order actions by (priority, Speed), then execute them one at a time.

Speed is re-evaluated after every action (Gen 8+), so Tailwind/Trick Room changes apply mid-turn.
Fainted mons are replaced between turns (`pending_replacements` / `replace`); a side with no living mon loses.
Accuracy, full-paralysis and spread moves are modeled; their coin flips come from `chance` (see Battle). Not yet
modeled: abilities/items beyond Choice Scarf Speed, secondary effects, evasion/accuracy stages. `moves.is_supported` is the gate: unsupported moves are rejected with ValueError before the turn runs.
"""
import random
from dataclasses import dataclass, field as dc_field
from typing import List

from ..calc import damage
from ..lookup import norm
from .moves import FIRST_TURN_ONLY, FLINCHES, SPREAD, all_moves, is_supported
from .state import make_field, make_pokemon

SWITCH_PRIORITY = 100  # switches resolve before every move
PROTECT, TRICK_ROOM, TAILWIND = "protect", "trickroom", "tailwind"
TRICK_ROOM_TURNS, TAILWIND_TURNS = 5, 4  # both count the turn they are used
FULL_PARALYSIS_PERCENT = 25
SPREAD_MODIFIER_TARGETS = 2  # a spread move is x0.75 once it hits this many targets


@dataclass
class TurnResult:
    order: List[str] = dc_field(default_factory=list)  # "slot:move" for each action that reached its turn
    flinched: List[str] = dc_field(default_factory=list)
    failed: List[str] = dc_field(default_factory=list)
    blocked: List[str] = dc_field(default_factory=list)  # attackers whose move hit a Protect
    missed: List[str] = dc_field(default_factory=list)  # attackers whose move missed a target (once per target)
    paralyzed: List[str] = dc_field(default_factory=list)  # attackers fully paralyzed this turn
    pending: List[str] = dc_field(default_factory=list)  # slots that need a replacement before the next turn
    log: List[str] = dc_field(default_factory=list)
    frames: List[dict] = dc_field(default_factory=list)  # {text, actor, target, state} per step, for scrubbing


def stage_multiplier(stage):
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def effective_speed(mon, side_tailwind):
    speed = int(mon.stats["speed"] * stage_multiplier(mon.boosts.get("speed", 0)))
    if mon.item == "choicescarf":
        speed = speed * 3 // 2
    if side_tailwind:
        speed *= 2
    if mon.status == "par":
        speed //= 2
    return speed


class Battle:
    def __init__(self, teams, active=1, field=None, seed=0, rolls="random", chance=None):
        """`rolls` picks the damage roll. `chance` forces the percent rolls (0-100) for accuracy and full-paralysis
        checks, consumed in order; once it runs out they come from the seeded rng. An accuracy check hits when
        roll < accuracy, full-paralysis stops the move when roll < 25. Moves that cannot miss consume nothing."""
        self.teams = {side: [make_pokemon(s) for s in specs] for side, specs in teams.items()}
        self.slots = {f"{side}{'ab'[i]}": (side, i) for side in self.teams for i in range(active)}
        self.active = {slot: i for slot, (_, i) in self.slots.items()}  # slot -> team index; None = empty slot
        self.field = make_field(field)
        self.rng = random.Random(seed)
        self.rolls = rolls
        self.chance = list(chance or [])
        self.moves = all_moves()
        self.turn_no = 0
        self.winner = None  # "p1", "p2", "draw" or None
        self._pending = []

    # -- lookups -------------------------------------------------------------------------------------------
    def mon(self, slot):
        i = self.active[slot]
        return None if i is None else self.teams[self.slots[slot][0]][i]

    def team_mon(self, ref):  # "p1:0" -> first mon of side p1, wherever it is
        side, idx = ref.split(":")
        return self.teams[side][int(idx)]

    def _alive(self, slot):
        m = self.mon(slot)
        return m is not None and m.hp > 0

    def _bench(self, side):
        in_play = {self.active[s] for s in self.slots if self.slots[s][0] == side}
        return [i for i, m in enumerate(self.teams[side]) if m.hp > 0 and i not in in_play]

    def pending_replacements(self):
        return list(self._pending)

    def _speed(self, slot):
        side = self.slots[slot][0]
        return effective_speed(self.mon(slot), self.field[f"tailwind_{side}"] > 0)

    def _priority(self, action):
        return SWITCH_PRIORITY if "switch" in action else self.moves[norm(action["move"])]["priority"]

    def _percent(self):
        return self.chance.pop(0) if self.chance else self.rng.random() * 100

    def _hits(self, accuracy):
        return accuracy is True or accuracy >= 100 or self._percent() < accuracy

    def _foes(self, slot):
        side = self.slots[slot][0]
        return [s for s in self.slots if self.slots[s][0] != side and self._alive(s)]

    # -- what the UI may offer -----------------------------------------------------------------------------
    def legal_actions(self, slot):
        empty = {"moves": [], "switches": []}
        if self.winner or slot in self._pending or not self._alive(slot):
            return empty
        side, mon, moves = self.slots[slot][0], self.mon(slot), []
        for move_id in mon.moves:
            if not is_supported(move_id):
                continue
            data = self.moves[move_id]
            targets = None
            if data["category"] != "Status" and data["target"] not in SPREAD:
                targets = [s for s in self.slots if s != slot and self._alive(s)
                           and (data["target"] != "adjacentFoe" or self.slots[s][0] != side)]
            moves.append({"move": move_id, "name": data["name"], "type": data["type"], "category": data["category"],
                          "priority": data["priority"], "targets": targets})
        return {"moves": moves, "switches": self._bench(side)}

    def snapshot(self):
        slots = {}
        for slot in self.slots:
            m = self.mon(slot)
            slots[slot] = None if m is None else {
                "index": self.active[slot], "species": m.species, "types": list(m.types), "hp": m.hp,
                "max_hp": m.max_hp, "status": m.status, "boosts": dict(m.boosts), "item": m.item,
                "ability": m.ability, "speed": self._speed(slot), "turns_out": m.turns_out}
        bench = {side: [{"index": i, "species": self.teams[side][i].species, "hp": self.teams[side][i].hp,
                         "max_hp": self.teams[side][i].max_hp} for i in self._bench(side)] for side in self.teams}
        return {"turn": self.turn_no, "field": dict(self.field), "winner": self.winner,
                "pending": list(self._pending), "slots": slots, "bench": bench}

    # -- turn ----------------------------------------------------------------------------------------------
    def _validate(self, actions):
        if self.winner:
            raise ValueError(f"the battle is over (winner: {self.winner})")
        if self._pending:
            raise ValueError(f"replacement needed first for: {', '.join(self._pending)}")
        for slot in self.slots:
            if self._alive(slot) and slot not in actions:
                raise ValueError(f"missing action for {slot}")
        switching = {side: [] for side in self.teams}
        for slot, a in actions.items():
            if slot not in self.slots:
                raise ValueError(f"unknown slot: {slot}")
            if not self._alive(slot):
                raise ValueError(f"{slot} has no living Pokémon to act")
            side, mon = self.slots[slot][0], self.mon(slot)
            if "switch" in a:
                if a["switch"] not in self._bench(side) or a["switch"] in switching[side]:
                    raise ValueError(f"{slot} cannot switch to team index {a['switch']}")
                switching[side].append(a["switch"])
                continue
            move_id = norm(a["move"])
            if move_id not in mon.moves:
                raise ValueError(f"{slot} ({mon.species}) does not know {a['move']}")
            if not is_supported(move_id):
                raise ValueError(f"{a['move']} is not implemented yet")
            legal = next(m for m in self.legal_actions(slot)["moves"] if m["move"] == move_id)
            if legal["targets"] is not None and a.get("target") not in legal["targets"]:
                raise ValueError(f"{slot} {move_id}: bad target {a.get('target')!r}, choose from {legal['targets']}")

    def turn(self, actions):
        self._validate(actions)
        self.turn_no += 1
        res = TurnResult()
        for slot in self.slots:
            if self._alive(slot):
                self.mon(slot).turns_out += 1
        self._frame(res, f"Turn {self.turn_no} starts")
        ties = {slot: self.rng.random() for slot in actions}
        queue = {slot: (self.mon(slot), a) for slot, a in actions.items()}
        moved = set()
        while queue:
            def key(slot):
                spd = self._speed(slot)
                return (-self._priority(queue[slot][1]), spd if self.field["trick_room"] else -spd, ties[slot])
            slot = min(queue, key=key)
            mon, action = queue.pop(slot)
            if mon.hp <= 0 or self.mon(slot) is not mon:
                continue
            text, target = self._act(slot, mon, action, res, moved)
            res.log.append(text)
            self._frame(res, text, slot, target)
            moved.add(id(mon))
        self._end_turn()
        self._settle()
        res.pending = list(self._pending)
        self._frame(res, "End of turn" if not self.winner else f"Battle over: {self.winner}")
        return res

    def _frame(self, res, text, actor=None, target=None):
        res.frames.append({"text": text, "actor": actor, "target": target, "state": self.snapshot()})

    def _retarget(self, slot, old_target):
        """Gen 5+ rule: if the chosen foe is gone, hit the remaining foe; an absent ally just fails."""
        side = self.slots[slot][0]
        if self.slots[old_target][0] == side:
            return None
        return next((s for s in self.slots if self.slots[s][0] != side and self._alive(s)), None)

    def _act(self, slot, mon, action, res, moved):
        """Run one action; returns (log text, target slot or None)."""
        if "switch" in action:
            res.order.append(f"{slot}:switch")
            self.active[slot] = action["switch"]
            self.mon(slot).turns_out = 0
            return f"{slot} switches to {self.mon(slot).species}", None
        move_id = norm(action["move"])
        move = self.moves[move_id]
        res.order.append(f"{slot}:{move_id}")
        if mon.flinched:
            res.flinched.append(slot)
            return f"{slot} {mon.species} flinched and couldn't move", None
        if move_id in FIRST_TURN_ONLY and mon.turns_out != 1:
            res.failed.append(slot)
            return f"{slot} {mon.species} used {move['name']}, but it failed", None
        if move["category"] == "Status":
            return self._status_move(slot, mon, move_id, res), None
        if mon.status == "par" and self._percent() < FULL_PARALYSIS_PERCENT:
            res.paralyzed.append(slot)
            return f"{slot} {mon.species} is fully paralyzed and couldn't move", None
        if move["target"] in SPREAD:
            targets = self._foes(slot) + ([s for s in self.slots if s != slot and self.slots[s][0] == self.slots[slot][0]
                                           and self._alive(s)] if move["target"] == "allAdjacent" else [])
            if not targets:
                return f"{slot} {mon.species} used {move['name']}, but there was no target", None
        else:
            target_slot = action["target"]
            if not self._alive(target_slot):
                target_slot = self._retarget(slot, target_slot)
                if target_slot is None:
                    return f"{slot} {mon.species} used {move['name']}, but there was no target", None
            targets = [target_slot]
        hit, notes = [], []
        for target_slot in targets:
            target = self.mon(target_slot)
            if target.protected and "protect" in move["flags"]:
                res.blocked.append(slot)
                notes.append(f"{target_slot} {target.species} protected itself from {move['name']}")
            elif not self._hits(move["accuracy"]):
                res.missed.append(slot)
                notes.append(f"{slot} {mon.species}'s {move['name']} missed {target_slot} {target.species}")
            else:
                hit.append(target_slot)
        spread = move["target"] in SPREAD and len(hit) >= SPREAD_MODIFIER_TARGETS
        for target_slot in hit:
            notes.append(self._hit(slot, mon, move_id, move, target_slot, spread, moved))
        return "; ".join(notes), (hit or targets)[0]

    def _hit(self, slot, mon, move_id, move, target_slot, spread, moved):
        target = self.mon(target_slot)
        rolls, _, _, _ = damage(mon.species, move_id, target.species, atk_nature=mon.nature, atk_sp=self._sp(mon),
                                def_nature=target.nature, def_sp=self._sp(target), item=mon.item,
                                ability=mon.ability, def_ability=target.ability, def_item=target.item,
                                doubles=len(self.slots) > 2, spread=spread)
        dealt = self.rng.choice(rolls) if self.rolls == "random" else {"max": max, "min": min}[self.rolls](rolls)
        dealt = min(dealt, target.hp)
        target.hp -= dealt
        text = f"{slot} {mon.species} used {move['name']} on {target_slot} {target.species} for {dealt}"
        if target.hp == 0:
            text += "; it fainted"
        elif move_id in FLINCHES and dealt and id(target) not in moved:
            target.flinched = True
        return text

    @staticmethod
    def _sp(mon):
        return ",".join(f"{k}={v}" for k, v in mon.sp.items()) or None

    def _status_move(self, slot, mon, move_id, res):
        side = self.slots[slot][0]
        if move_id == PROTECT:
            mon.protected = True
        elif move_id == TRICK_ROOM:
            self.field["trick_room"] = 0 if self.field["trick_room"] else TRICK_ROOM_TURNS
        elif move_id == TAILWIND:
            if self.field[f"tailwind_{side}"]:
                res.failed.append(slot)
            else:
                self.field[f"tailwind_{side}"] = TAILWIND_TURNS
        else:
            raise NotImplementedError(f"status move not implemented: {move_id}")
        return f"{slot} {mon.species} used {self.moves[move_id]['name']}"

    def _end_turn(self):
        for key in ("trick_room", "tailwind_p1", "tailwind_p2"):
            self.field[key] = max(0, self.field[key] - 1)
        for slot in self.slots:
            m = self.mon(slot)
            if m is not None:
                m.flinched = False
                m.protected = False

    # -- fainting ------------------------------------------------------------------------------------------
    def _settle(self):
        """After a turn: queue replacements for fainted slots (empty the slot if no reserve is left) and decide a winner."""
        self._pending = []
        used = {side: 0 for side in self.teams}
        for slot in self.slots:
            m = self.mon(slot)
            if m is not None and m.hp <= 0:
                side = self.slots[slot][0]
                if len(self._bench(side)) > used[side]:
                    used[side] += 1
                    self._pending.append(slot)
                else:
                    self.active[slot] = None
        out = [side for side, team in self.teams.items() if not any(m.hp > 0 for m in team)]
        if out:
            self.winner = "draw" if len(out) > 1 else next(s for s in self.teams if s not in out)
            self._pending = []

    def replace(self, slot, team_index):
        if slot not in self._pending:
            raise ValueError(f"{slot} does not need a replacement")
        side = self.slots[slot][0]
        if team_index not in self._bench(side):
            raise ValueError(f"{slot} cannot be replaced by team index {team_index}")
        self.active[slot] = team_index
        self.mon(slot).turns_out = 0
        self._pending.remove(slot)
