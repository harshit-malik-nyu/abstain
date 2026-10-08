#!/usr/bin/env python3
"""
Prove the holdout was opened once, not twice.

What happened
-------------
The confirmatory holdout run was killed partway through by the session it was
running in, during the last tolerance. No output file was written. Everything
before that point had already been printed, and therefore already seen:
the replication table, the concentration breakdown, and the scheme comparison
at alpha = 0.20 and 0.15.

Re-running looks exactly like a second look at a holdout, which is the thing
this repository is built to prevent. The distinction is real but it is not
worth anything unless it is checked:

    A second LOOK would be a second DRAW -- different trials, a fresh chance
    for something to come out favourably, and the right to pick which run to
    report.

    A resumed run is the SAME draw. The seed is fixed in the script, the
    script was last modified before the first run, and nothing between the
    two touched the benchmark.

So the claim is checkable, and this checks it: every row the interrupted run
printed must appear, character for character, in the completed run. If one
number moved, the two are different experiments and the result should be
thrown away rather than explained.

`evidence/round4-holdout-partial-interrupted.txt` is the interrupted log,
committed before the relaunch so it cannot be edited to match afterwards.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PARTIAL = ROOT / "evidence" / "round4-holdout-partial-interrupted.txt"
COMPLETE = ROOT / "evidence" / "round4-holdout-run.txt"

# Lines carrying numbers. Headers and rules are skipped: they are identical by
# construction and their presence would dilute the check.
NUMERIC = re.compile(r"\d")


def rows(path: Path) -> list[str]:
    out = []
    for line in path.read_text().splitlines():
        s = " ".join(line.split())
        if not s or not NUMERIC.search(s):
            continue
        if s.startswith("---") or "----" in s:
            continue
        # The elapsed-time line legitimately differs between the two runs and
        # is the only such line; excluding it by name rather than by pattern,
        # so a second differing line would still fail the check.
        if s.startswith("wrote evidence/"):
            continue
        out.append(s)
    return out


def main() -> int:
    if not PARTIAL.exists():
        print(f"  {PARTIAL.relative_to(ROOT)} missing — nothing to verify")
        return 1
    if not COMPLETE.exists():
        print(f"  {COMPLETE.relative_to(ROOT)} missing — "
              "the resumed run has not finished")
        return 1

    before, after = rows(PARTIAL), rows(COMPLETE)
    missing = [r for r in before if r not in after]

    print(f"  interrupted run: {len(before)} numeric lines")
    print(f"  completed run:   {len(after)} numeric lines")
    print(f"  lines from the interrupted run absent from the completed one: "
          f"{len(missing)}")

    if missing:
        print("\n  THE TWO RUNS DISAGREE. They are different experiments and")
        print("  the holdout has been opened twice. Do not report this.\n")
        for line in difflib.unified_diff(before, after, "interrupted",
                                         "completed", lineterm="", n=1):
            print(f"    {line}")
        return 1

    print("\n  Every row the interrupted run printed reappears unchanged.")
    print("  One draw, run in two pieces. The holdout was opened once.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
