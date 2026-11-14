"""The mechanic catalogue is internally consistent, and the checker catches breakage."""
import unittest

from champions.catalogue import load


def mech(id, deps=(), cases=()):
    return {"id": id, "depends_on": list(deps), "cases": list(cases)}


def case(id, kind="positive", status="ok"):
    return {"id": id, "group": "g", "kind": kind, "status": status, "setup": "s", "expect": "e"}


class RealCatalogue(unittest.TestCase):
    def test_real_files_are_consistent(self):
        self.assertEqual(load.check_catalogue(), [])

    def test_every_mechanic_has_needs_list(self):
        for m in load.load_mechanics():
            self.assertIsInstance(m.get("needs"), list, m["id"])


class Checker(unittest.TestCase):
    def test_cycle_is_rejected(self):
        probs = load.check_catalogue([mech("a", ["b"]), mech("b", ["a"])], [])
        self.assertTrue(any("cycle" in p for p in probs), probs)

    def test_unknown_dependency_is_rejected(self):
        probs = load.check_catalogue([mech("a", ["nope"])], [])
        self.assertTrue(any("unknown mechanic" in p for p in probs), probs)

    def test_duplicate_ids_are_rejected(self):
        probs = load.check_catalogue([mech("a"), mech("a")], [])
        self.assertTrue(any("duplicate mechanic" in p for p in probs), probs)

    def test_bad_case_is_rejected(self):
        bad = case("x", kind="weird")
        probs = load.check_catalogue([mech("a", cases=[bad, case("x")])], [])
        self.assertTrue(any("bad kind" in p for p in probs), probs)
        self.assertTrue(any("duplicate case id" in p for p in probs), probs)

    def test_involves_must_be_subset_of_uses(self):
        comp = {"id": "c", "uses": ["a"], "depends_on": [],
                "cases": [dict(case("k"), involves=["a", "b"])]}
        probs = load.check_catalogue([mech("a"), mech("b")], [comp])
        self.assertTrue(any("not in uses" in p for p in probs), probs)

    def test_find_cycle_returns_path(self):
        self.assertEqual(load.find_cycle({"a": ["b"], "b": ["c"], "c": ["a"]})[0], "a")
        self.assertIsNone(load.find_cycle({"a": ["b"], "b": []}))


if __name__ == "__main__":
    unittest.main()
