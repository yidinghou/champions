import unittest
from unittest import mock

from champions.live import scout, server, solve

TEAM = server.load_team("examples/my_team_doubles.json")


def board(**kw):
    req = {"mine": [{"name": "incineroar", "hp": 1}, {"name": "garchomp", "hp": 1}],
           "mine_bench": [{"name": "venusaur", "hp": 1}],
           "foes": [{"name": "gengar", "hp": 1}, {"name": "dragonite", "hp": 1}],
           "foe_bench": [{"name": "gyarados", "hp": 1}]}
    req.update(kw)
    return req


class SolveLive(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(solve, "WORKERS", 1)       # no worker processes in tests
        p.start()
        self.addCleanup(p.stop)

    def test_returns_lines_a_foe_reply_and_what_it_left_out(self):
        out = solve.solve_live(board(), TEAM, budget=20)
        self.assertEqual(out["label"], "2 turns")
        self.assertTrue(out["lines"])
        self.assertAlmostEqual(sum(l["p"] for l in out["lines"]), 1.0, places=1)
        self.assertEqual(len(out["lines"][0]["actions"]), 2)           # one action per active Pokemon
        self.assertTrue(out["foe_replies"])
        self.assertTrue(any(u["kind"] == "move" for u in out["unmodeled"]))   # e.g. Perish Song is not modeled

    def test_returns_the_one_turn_matrix(self):
        out = solve.solve_live(board(), TEAM, budget=20)
        n, m = len(out["rows"]), len(out["cols"])
        self.assertEqual((len(out["matrix"]), len(out["matrix"][0])), (n, m))
        self.assertEqual((len(out["row_mix"]), len(out["col_mix"])), (n, m))
        self.assertAlmostEqual(sum(out["row_mix"]), 1.0, places=1)
        self.assertAlmostEqual(sum(out["col_mix"]), 1.0, places=1)
        self.assertEqual(len(out["rows"][0]), 2)
        # the game value is what the mixes get out of the matrix
        v = sum(out["row_mix"][i] * out["col_mix"][j] * out["matrix"][i][j]
                for i in range(n) for j in range(m) if out["matrix"][i][j] is not None)
        self.assertAlmostEqual(v, out["value"], places=1)

    def test_cells_show_the_end_state_of_each_plan_pair(self):
        out = solve.solve_live(board(), TEAM, budget=20)
        n, m = len(out["rows"]), len(out["cols"])
        self.assertEqual((len(out["cells"]), len(out["cells"][0])), (n, m))
        for row in out["cells"]:
            for cell in row:
                self.assertEqual([s["side"] for s in cell["slots"]], ["foe"] * 2 + ["me"] * 2)
                for sl in cell["slots"]:
                    self.assertTrue(0 <= sl["ko"] <= 1 and 0 <= sl["lo"] <= sl["hi"] <= 1)
                self.assertAlmostEqual(cell["you_ko"], sum(s["ko"] for s in cell["slots"] if s["side"] == "foe"), places=2)
        for key in ("row_vs", "row_worst", "row_worst_col"):
            self.assertEqual(len(out[key]), n)
        self.assertIn(out["best"], range(n))
        self.assertIn(out["safe"], range(n))
        self.assertTrue(all("type" in a for r in out["rows"] for a in r if a["kind"] == "move"))

    def test_a_switch_shows_the_pokemon_coming_in(self):
        out = solve.solve_live(board(), TEAM, budget=20)
        for i, row in enumerate(out["rows"]):
            for k, act in enumerate(row):
                if act["kind"] == "switch":
                    slots = [s for s in out["cells"][i][0]["slots"] if s["side"] == "me"]
                    self.assertTrue(slots[k]["incoming"])
                    self.assertEqual(slots[k]["name"], act["to"])
                    return
        self.skipTest("no switch among the candidate rows")

    def test_bench_lets_a_switch_be_a_line(self):
        out = solve.solve_live(board(), TEAM, budget=20)
        kinds = {a["kind"] for l in out["lines"] for a in l["actions"]}
        self.assertIn("move", kinds)

    def test_needs_someone_on_each_side(self):
        with self.assertRaises(scout.BadBoard):
            solve.build(board(foes=[]), TEAM)
        with self.assertRaises(scout.BadBoard):
            solve.build(board(mine=[]), TEAM)

    def test_fainted_active_is_not_on_the_field(self):
        b, placed, _ = solve.build(board(mine=[{"name": "incineroar", "hp": 1}, {"name": "garchomp", "hp": 0}]), TEAM)
        self.assertEqual([m.species for w, _, m in placed if w == "me"], ["incineroar"])
        self.assertEqual(b.sides[0].active, [0, None])

    def test_stages_come_from_the_page_not_the_engine(self):
        b, _, _ = solve.build(board(mine=[{"name": "incineroar", "hp": 1, "boosts": {"atk": 2}}, {"name": "garchomp", "hp": 1}]), TEAM)
        self.assertEqual(b.sides[0].team[0].stages["atk"], 2)
        self.assertEqual(b.sides[1].team[0].stages["atk"], 0)


if __name__ == "__main__":
    unittest.main()
