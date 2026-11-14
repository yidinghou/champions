"""Every runnable catalogue stub is a test. Filter with CHAMPIONS_CASE=<substring of mechanic::case>."""
import os
import unittest

from champions.catalogue.cases import case_name, runnable_cases
from champions.catalogue.runner import format_failure, run_case


class CatalogueCases(unittest.TestCase):
    def test_cases(self):
        only = os.environ.get("CHAMPIONS_CASE", "")
        for owner, case in runnable_cases():
            name = case_name(owner, case)
            if only not in name:
                continue
            with self.subTest(name):
                res = run_case(owner, case)
                if not res.passed:
                    self.fail("\n" + format_failure(res))


if __name__ == "__main__":
    unittest.main()
