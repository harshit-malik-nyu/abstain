#!/usr/bin/env python3
"""
Open the holdout. Once.

Everything about the method was frozen in the preceding commit and the
predictions are in docs/preregistration.md. This script changes nothing except
which file it reads.

It is deliberately a copy of the dev analysis with one substitution, so that a
reader can diff the two and see that no parameter moved.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.scorer import handcrafted_scorer          # noqa: E402
from abstain.validate import validate                  # noqa: E402

ALPHAS = (0.20, 0.15, 0.10, 0.05)
TRIALS = 150
SEED = 3


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "holdout.json").read_text())
    print(f"  holdout: {len(cases)} cases\n")
    print(f"  {'alpha':>6s} {'violations':>11s} {'infeasible':>11s} "
          f"{'coverage':>9s} {'Q/case':>7s} {'holds':>6s}")

    out = {}
    for a in ALPHAS:
        v = validate(cases, handcrafted_scorer, alpha=a, delta=0.05,
                     trials=TRIALS, seed=SEED, unit="trajectory")
        d = v.as_dict()
        out[str(a)] = d
        print(f"  {a:>6.2f} {d['violation_rate']:>10.1%} "
              f"{d['infeasible_rate']:>10.0%} {d['mean_coverage']:>9.1%} "
              f"{d['mean_questions']:>7.2f} "
              f"{'yes' if d['holds'] else 'NO':>6s}")

    (ROOT / "evidence" / "holdout_result.json").write_text(
        json.dumps({"cases": len(cases), "trials": TRIALS, "seed": SEED,
                    "results": out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
