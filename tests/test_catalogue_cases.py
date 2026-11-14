"""Every runnable catalogue stub is a test. Filter with CHAMPIONS_CASE=<substring of mechanic::case>."""
import os
import unittest

from champions.catalogue import report
from champions.catalogue.cases import case_name, runnable_cases
from champions.catalogue.load import load_mechanics
from champions.catalogue.runner import format_failure, run_all, upstream_failing

# Mechanics the engine models. Each must have a runnable positive, control and interaction case.
MODELED = ["type-immunity", "protect", "stat-stages", "foe-stat-drop", "entry-trigger", "first-turn-only",
           "flinch", "move-priority", "self-drop", "secondary-effect", "recoil-drain-heal",
           "accuracy-evasion", "crit", "multi-hit", "target-resolution", "move-pipeline", "major-status"]


class CatalogueCases(unittest.TestCase):
    def test_cases(self):
        only = os.environ.get("CHAMPIONS_CASE", "")
        pairs = [(o, c) for o, c in runnable_cases() if only in case_name(o, c)]
        results = run_all(pairs)
        mechanics = load_mechanics()
        for res in results:
            with self.subTest(case_name(res.owner, res.case)):
                if not res.passed:
                    self.fail("\n" + format_failure(res, upstream_failing(res.owner, results, mechanics)))


class Coverage(unittest.TestCase):
    def test_modeled_mechanics_have_all_three_kinds(self):
        rows = {r["id"]: r for r in report.build()}
        for mid in MODELED:
            with self.subTest(mid):
                self.assertEqual(rows[mid]["missing"], [], f"{mid} lacks runnable {rows[mid]['missing']} cases")

    def test_verify_cases_are_skipped_by_default(self):
        default = {case_name(o, c) for o, c in runnable_cases(verify=False)}
        everything = {case_name(o, c) for o, c in runnable_cases(verify=True)}
        self.assertTrue(default < everything)
        self.assertTrue(all("verify" != c["status"] for o, c in runnable_cases(verify=False)))


if __name__ == "__main__":
    unittest.main()
