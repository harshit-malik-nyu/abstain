#!/usr/bin/env python3
"""
Does the fix the diagnosis implies actually work?

`docs/preregistration-5.md`, addendum six, committed before `award_aware_scorer`
existed. M1–M5 are fixed there and `AWARD_RISK_WEIGHT = 0.8` is fixed in the
scorer; neither is adjusted after seeing a result.

Every repair measured before this one works *around* the defect — group
conditioning gives the failing band its own threshold, removing the distance
feature blinds the scorer everywhere. This one addresses the defect itself: a
missing feature for how much the award could move.

If it does not work, the diagnosis is wrong or incomplete despite two
independent measurements supporting it, and that goes at the top of the README.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import Breakdown, collector  # noqa: E402
from abstain.group import validate_groups  # noqa: E402
from abstain.scorer import (auc, award_aware_scorer,  # noqa: E402
                            handcrafted_scorer)
from abstain.validate import states_of, validate  # noqa: E402

ALPHAS = (0.20, 0.15)
TRIALS = 200
SEED = 83
CALIBRATION_SHARE = 0.30

SCORERS = (("handcrafted", handcrafted_scorer),
           ("award-aware", award_aware_scorer))


def measure(cases: list[dict], label: str, scorer) -> list[dict]:
    rows = states_of(cases)
    a = auc([(scorer(c, k), d) for c, k, d in rows])
    print(f"\n  {label}: AUC {a:.4f}")

    out = []
    for alpha in ALPHAS:
        bd = Breakdown(alpha=alpha)
        v = validate(cases, scorer, alpha=alpha, trials=TRIALS, seed=SEED,
                     calibration_share=CALIBRATION_SHARE,
                     on_trial=collector(bd))
        d = bd.as_dict() | {"scorer": label, "auc": a,
                            "mean_coverage": v.mean_coverage,
                            "mean_questions": v.mean_questions,
                            "violation_rate_when_feasible":
                                v.violation_rate_when_feasible}
        out.append(d)

        worst = d["worst_band"]
        conc = d["concentration"].get(worst, 0.0) if worst else 0.0
        print(f"\n  {label}, alpha = {alpha:.2f}   pooled "
              f"{bd.pooled_unsafe_rate:.1%}   coverage {v.mean_coverage:.1%}"
              f"   q/case {v.mean_questions:.2f}")
        print(f"  worst band {worst}   concentration {conc:.2f}   "
              f"hides a subgroup: {bd.hides_a_subgroup}")
        print(f"  {'band':>16} {'unsafe':>8} {'cov':>8} {'conc':>7}")
        for row in d["bands"]:
            print(f"  {row['band']:>16} {row['unsafe_rate']:>7.1%} "
                  f"{row['coverage']:>7.1%} "
                  f"{d['concentration'][row['band']]:>7.2f}")
    return out


def conditioning(cases: list[dict]) -> list[dict]:
    """M5: how much is left for group conditioning to fix?"""
    print("\n  M5 — what does group conditioning still add?")
    print(f"  {'scorer':>13} {'alpha':>6} {'scheme':>10} {'feas':>6} "
          f"{'grp-viol':>9} {'worst':>7} {'cov':>7}")
    out = []
    for label, scorer in SCORERS:
        for alpha in ALPHAS:
            for scheme in ("pooled", "by-band"):
                v = validate_groups(cases, scorer, scheme=scheme,
                                    alpha=alpha, trials=TRIALS, seed=SEED,
                                    calibration_share=CALIBRATION_SHARE)
                d = v.as_dict() | {"scorer": label}
                out.append(d)
                gv = d["group_violation_rate_when_feasible"]
                print(f"  {label:>13} {alpha:>6.2f} {scheme:>10} "
                      f"{d['feasible_trials']:>6} "
                      f"{'n/a' if gv is None else f'{gv:.1%}':>9} "
                      f"{d['mean_worst_group_rate']:>6.1%} "
                      f"{d['mean_coverage']:>6.1%}")
        print()
    return out


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}")
    print("  AWARD_RISK_WEIGHT = 0.8, fixed in the pre-registration")

    t0 = time.time()
    arms = {label: measure(cases, label, scorer) for label, scorer in SCORERS}
    schemes = conditioning(cases)

    print("\n  M1-M4 — side by side at alpha = 0.20")
    print(f"  {'scorer':>13} {'AUC':>7} {'pooled':>8} {'cov':>7} "
          f"{'worst band':>15} {'its rate':>9} {'conc':>7}")
    for label in arms:
        d = next(r for r in arms[label] if r["alpha"] == 0.20)
        w = next(b for b in d["bands"] if b["band"] == d["worst_band"])
        print(f"  {label:>13} {d['auc']:>7.4f} "
              f"{d['pooled_unsafe_rate']:>7.1%} {d['mean_coverage']:>6.1%} "
              f"{str(d['worst_band']):>15} {w['unsafe_rate']:>8.1%} "
              f"{d['concentration'][d['worst_band']]:>7.2f}")

    payload = {"set": "fine_dev", "trials": TRIALS, "seed": SEED,
               "calibration_share": CALIBRATION_SHARE,
               "award_risk_weight": 0.8,
               "arms": {k: v for k, v in arms.items()},
               "schemes": schemes,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "award_aware.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
