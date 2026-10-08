#!/usr/bin/env python3
"""
Run the three pre-registered secondary experiments. Dev only.

Order
-----
`docs/preregistration-2.md` was committed before this file existed, and the
git history shows it. The predictions, the seeds, the tolerances and the
conditions are all fixed there; this script executes them and writes the
numbers out. It does not choose anything.

Holdout is not touched here. The one reserved holdout look, for prediction B1,
lives in `scripts/open_holdout_2.py` and is run once.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import (Breakdown, collector, population_shares,  # noqa: E402
                                 undetermined_share)
from abstain.robustness import ordering_quality, rank_correlation, suite  # noqa: E402
from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

ALPHAS = (0.20, 0.15, 0.10)
TRIALS = 150
SEED_A, SEED_B, SEED_C = 11, 13, 17
CAL_SIZES = (20, 30, 40, 50)


def experiment_a(dev: list[dict]) -> dict:
    """The plug-in baseline, at matched tolerance and across calibration size."""
    print("\n  A — the plug-in baseline")
    print("  " + "-" * 68)
    print(f"  {'alpha':>6} {'bound':>16} {'viol':>7} {'infeas':>7} "
          f"{'cov':>7} {'q/case':>7}")

    matched = []
    for alpha in ALPHAS:
        for bound in ("clopper-pearson", "plugin"):
            v = validate(dev, handcrafted_scorer, alpha=alpha, trials=TRIALS,
                         seed=SEED_A, bound=bound)
            row = v.as_dict() | {"bound": bound}
            matched.append(row)
            print(f"  {alpha:>6.2f} {bound:>16} {v.violation_rate:>6.1%} "
                  f"{v.infeasible_rate:>6.1%} {v.mean_coverage:>6.1%} "
                  f"{v.mean_questions:>7.2f}")

    print("\n  calibration-size sweep at alpha = 0.10")
    print(f"  {'n_cal':>6} {'bound':>16} {'viol':>7} {'infeas':>7} {'cov':>7}")
    sweep = []
    for n_cal in CAL_SIZES:
        for bound in ("clopper-pearson", "plugin"):
            v = validate(dev, handcrafted_scorer, alpha=0.10, trials=TRIALS,
                         seed=SEED_A, bound=bound, calibration_size=n_cal)
            row = v.as_dict() | {"bound": bound, "calibration_size": n_cal}
            sweep.append(row)
            print(f"  {n_cal:>6} {bound:>16} {v.violation_rate:>6.1%} "
                  f"{v.infeasible_rate:>6.1%} {v.mean_coverage:>6.1%}")

    return {"matched": matched, "calibration_size_sweep": sweep,
            "trials": TRIALS, "seed": SEED_A}


def experiment_b(dev: list[dict]) -> dict:
    """Does the bound survive a bad score?"""
    print("\n  B — score corruption")
    print("  " + "-" * 68)

    corruptions = suite(handcrafted_scorer, seed=SEED_B)
    base = corruptions[0].scorer

    print(f"  {'corruption':>16} {'AUC':>7} {'tau':>7}   ordering vs identity")
    quality = []
    for c in corruptions:
        a = ordering_quality(dev, c.scorer)
        tau = rank_correlation(dev, base, c.scorer)
        quality.append({"name": c.name, "auc": a, "kendall_tau": tau,
                        "note": c.note})
        print(f"  {c.name:>16} {a:>7.4f} {tau:>7.4f}   {c.note}")

    print(f"\n  {'corruption':>16} {'alpha':>6} {'viol':>7} {'infeas':>7} "
          f"{'cov':>7} {'q/case':>7}")
    runs = []
    for c in corruptions:
        for alpha in ALPHAS:
            v = validate(dev, c.scorer, alpha=alpha, trials=TRIALS,
                         seed=SEED_B)
            runs.append(v.as_dict() | {"corruption": c.name})
            print(f"  {c.name:>16} {alpha:>6.2f} {v.violation_rate:>6.1%} "
                  f"{v.infeasible_rate:>6.1%} {v.mean_coverage:>6.1%} "
                  f"{v.mean_questions:>7.2f}")

    return {"ordering": quality, "runs": runs, "trials": TRIALS,
            "seed": SEED_B}


def experiment_c(dev: list[dict]) -> dict:
    """Is the budget spent uniformly across income bands?"""
    print("\n  C — conditional coverage by income band")
    print("  " + "-" * 68)

    shares = population_shares(dev)
    opens = undetermined_share(dev)
    print(f"  {'band':>16} {'pop share':>10} {'states open':>12}")
    for b, s in shares.items():
        print(f"  {b:>16} {s:>10.1%} {opens.get(b, 0.0):>12.1%}")

    out = []
    for alpha in ALPHAS:
        bd = Breakdown(alpha=alpha)
        validate(dev, handcrafted_scorer, alpha=alpha, trials=TRIALS,
                 seed=SEED_C, on_trial=collector(bd))
        d = bd.as_dict()
        out.append(d)
        print(f"\n  alpha = {alpha:.2f}   pooled unsafe "
              f"{bd.pooled_unsafe_rate:.1%}   "
              f"hides a subgroup: {bd.hides_a_subgroup}")
        print(f"  {'band':>16} {'deployed':>9} {'unsafe':>7} "
              f"{'rate':>7} {'cov':>7} {'concentration':>14}")
        for row in d["bands"]:
            print(f"  {row['band']:>16} {row['deployed']:>9} "
                  f"{row['unsafe']:>7} {row['unsafe_rate']:>6.1%} "
                  f"{row['coverage']:>6.1%} "
                  f"{d['concentration'][row['band']]:>14.2f}")

    return {"population_shares": shares, "undetermined_share": opens,
            "breakdowns": out, "trials": TRIALS, "seed": SEED_C}


def main() -> int:
    dev = json.loads((ROOT / "evidence" / "dev.json").read_text())
    print(f"  dev: {len(dev)} cases, {TRIALS} trials per condition")
    print("  holdout is not read by this script")

    t0 = time.time()
    payload = {
        "set": "dev",
        "n_cases": len(dev),
        "alphas": list(ALPHAS),
        "A_plugin_baseline": experiment_a(dev),
        "B_score_corruption": experiment_b(dev),
        "C_conditional_coverage": experiment_c(dev),
    }
    payload["elapsed_seconds"] = round(time.time() - t0, 1)

    dest = ROOT / "evidence" / "secondary_dev.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
