#!/usr/bin/env python3
"""
Does the relaunched round-R run reproduce the interrupted one, draw for draw?

Why this exists
---------------
Round R's first attempt was killed at draw 32 of 40. The claim that makes a
relaunch legitimate rather than a second look is that **each draw is a pure
function of its seed** — the bootstrap resample, the trial splits and both
arms are all seeded from `ROOT_SEED + b`, fixed in addendum ten before the
first run.

That claim is checkable, so it is checked. `evidence/pool-bootstrap-interrupted.txt`
was committed *before* the relaunch, so it cannot have been edited to agree
afterwards — the same discipline `verify_resumed_run.py` enforces for round
four's interrupted holdout run.

What a mismatch would mean
--------------------------
That something in the path is not seeded: a set iteration order, a `hash()`,
a dict ordering, a global RNG consumed elsewhere. This repository has already
shipped one such defect — `robustness.noisy` seeded from `hash()`, which
Python salts per process — so it is not a hypothetical. If any draw differs,
the relaunch is a second experiment and the result should be discarded rather
than explained.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OLD = ROOT / "evidence" / "pool-bootstrap-interrupted.txt"
NEW = ROOT / "evidence" / "pool-bootstrap-run.txt"

# "  draw  9/40  pooled  95.0%  by-band  10.6%  (feasible 100 /  66)"
DRAW = re.compile(
    r"^\s*draw\s+(\d+)/(\d+)\s+pooled\s+(\S+)\s+by-band\s+(\S+)\s+"
    r"\(feasible\s+(\d+)\s*/\s*(\d+)\)")


def rows(path: Path) -> dict[int, tuple[str, str, str, str]]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text().splitlines():
        m = DRAW.match(line)
        if m:
            out[int(m.group(1))] = (m.group(3), m.group(4),
                                    m.group(5), m.group(6))
    return out


def main() -> int:
    old, new = rows(OLD), rows(NEW)
    if not old:
        print(f"  no interrupted log at {OLD.relative_to(ROOT)}; nothing to "
              f"verify")
        return 0
    if not new:
        print(f"  no completed log at {NEW.relative_to(ROOT)} yet")
        return 1

    shared = sorted(set(old) & set(new))
    print(f"  interrupted log: {len(old)} draws")
    print(f"  current log:     {len(new)} draws")
    print(f"  overlapping:     {len(shared)}\n")

    bad = []
    for d in shared:
        if old[d] != new[d]:
            bad.append((d, old[d], new[d]))

    if bad:
        print("  MISMATCH — the relaunch is a different experiment:\n")
        for d, o, n in bad:
            print(f"    draw {d}: interrupted {o}  current {n}")
        return 1

    print(f"  every one of the {len(shared)} overlapping draws matches "
          f"character for character.")
    print("  The relaunch is the same draw, not a second look.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
