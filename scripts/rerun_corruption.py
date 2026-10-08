#!/usr/bin/env python3
"""
Experiment B again, after the refusal threshold was fixed.

Why this is a separate script and a separate evidence file
----------------------------------------------------------
The first run of experiment B found a safety bug: the threshold calibration
falls back to when it declines to certify itself was 1.0, and `run_case`
commits on `score >= threshold`, so any score with a point mass at exactly 1.0
cleared it. Under the anti-correlated scorer 792 of the 796 states sitting at
1.0 were undetermined, and the rule committed blind on them in 100% of trials.

Predictions B1 and B4 failed on that run. They failed because of the defect
rather than because of the theory, and the distinction is only credible if
both runs survive. So the pre-fix run is kept verbatim in
`evidence/secondary-prefix-run.txt` and `evidence/secondary_dev_prefix.json`,
this one is written separately, and the write-up reports both.

Fixing a bug and re-running is not the same as tuning, and the line between
them is worth stating rather than assuming. The change corrected code that did
not implement what it was documented to implement — "the most conservative
threshold" was not conservative. No parameter moved, no tolerance moved, no
corruption was added or dropped, and the predictions are the ones already
written down in `docs/preregistration-2.md`. A reader who disagrees can
compare the two evidence files.

What also changed, and why it matters more than the sentinel
-----------------------------------------------------------
`Validation` now reports the violation rate over **feasible** trials
separately from the rate over all trials. The guarantee was always conditional
on feasibility — the procedure either issues a threshold that holds alpha or
reports that none does — and scoring a declined trial against a bound the
method refused to issue measures obedience to the flag rather than the bound.

That distinction was invisible while every condition was feasible. The
corruption study made it load-bearing: under `constant` and `inverted` the
procedure declines in 100% of trials, and the honest statement about those
trials is that there is no guarantee to test. Not that it held. Not that it
failed.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.robustness import (ordering_quality, rank_correlation,  # noqa: E402
                                suite)
from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

ALPHAS = (0.20, 0.15, 0.10)
TRIALS = 150
SEED_B = 13


def main() -> int:
    dev = json.loads((ROOT / "evidence" / "dev.json").read_text())
    corruptions = suite(handcrafted_scorer, seed=SEED_B)
    base = corruptions[0].scorer
    t0 = time.time()

    print(f"  dev: {len(dev)} cases, {TRIALS} trials, seed {SEED_B}")
    print("  post-fix: the refusal threshold is now outside the score range\n")
    print(f"  {'corruption':>16} {'alpha':>6} {'feas':>6} {'viol|feas':>10} "
          f"{'viol(all)':>10} {'infeas':>7} {'cov':>7} {'holds':>6}")

    runs = []
    for c in corruptions:
        a = ordering_quality(dev, c.scorer)
        tau = rank_correlation(dev, base, c.scorer)
        for alpha in ALPHAS:
            v = validate(dev, c.scorer, alpha=alpha, trials=TRIALS,
                         seed=SEED_B)
            d = v.as_dict() | {"corruption": c.name, "auc": a,
                               "kendall_tau": tau, "note": c.note}
            runs.append(d)
            vf = d["violation_rate_when_feasible"]
            print(f"  {c.name:>16} {alpha:>6.2f} "
                  f"{d['feasible_trials']:>6} "
                  f"{'n/a' if vf is None else f'{vf:.1%}':>10} "
                  f"{d['violation_rate']:>9.1%} "
                  f"{d['infeasible_rate']:>6.1%} {d['mean_coverage']:>6.1%} "
                  f"{str(d['holds']):>6}")

    payload = {"set": "dev", "n_cases": len(dev), "trials": TRIALS,
               "seed": SEED_B, "phase": "post-fix", "runs": runs,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "corruption_postfix.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
