"""champions catalogue status [--verify]   coverage of the mechanic catalogue; exit 1 if a case fails."""
import sys

from . import report
from .load import check_catalogue


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] != "status":
        sys.exit("usage: champions catalogue status [--verify]")
    problems = check_catalogue()
    if problems:
        sys.exit("catalogue is inconsistent:\n  " + "\n  ".join(problems))
    rows = report.build(verify=True if "--verify" in argv else None)
    print(report.format_table(rows))
    if any(r["failing"] for r in rows):
        sys.exit(1)
