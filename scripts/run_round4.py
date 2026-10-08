#!/usr/bin/env python3
"""
Round four: the replication, and the subgroup experiment done properly.

Order
-----
`docs/preregistration-4.md` was committed before this file existed and before
either half of the fine benchmark had been read. Every parameter below is
fixed there — 400 trials, calibration share 0.30, seed 31, the three
tolerances, the three schemes. This script executes and reports.

Run twice: `--set dev` first, then `--set holdout` once. The coarse
benchmark's holdout is not read by this script at all.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import (Breakdown, collector, population_shares,  # noqa: E402
                                 undetermined_share)
from abstain.group import SCHEMES, validate_groups  # noqa: E402
from abstain.power import shortfall  # noqa: E402
from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

# Pre-registered in docs/preregistration-4.md. Not arguments.
TRIALS = 400
CALIBRATION_SHARE = 0.30
SEED = 31
PRIMARY_ALPHAS = (0.20, 0.15)
EXPLORATORY_ALPHAS = (0.10,)
ALPHAS = PRIMARY_ALPHAS + EXPLORATORY_ALPHAS


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def replication(cases: list[dict]) -> list[dict]:
    """E1 and E2: does the pooled rule's guarantee hold on this benchmark?"""
    print("\n  E1/E2 — the pooled rule, replicated")
    print("  " + "-" * 76)
    print(f"  {'alpha':>6} {'feas':>6} {'viol|feas':>10} {'viol(all)':>10} "
          f"{'infeas':>7} {'cov':>7} {'q/case':>7} {'holds':>6}")

    out = []
    for alpha in ALPHAS:
        v = validate(cases, handcrafted_scorer, alpha=alpha, trials=TRIALS,
                     seed=SEED, calibration_share=CALIBRATION_SHARE)
        d = v.as_dict() | {"powered": alpha in PRIMARY_ALPHAS}
        out.append(d)
        print(f"  {alpha:>6.2f} {d['feasible_trials']:>6} "
              f"{fmt(d['violation_rate_when_feasible']):>10} "
              f"{d['violation_rate']:>9.1%} {d['infeasible_rate']:>6.1%} "
              f"{d['mean_coverage']:>6.1%} {d['mean_questions']:>7.2f} "
              f"{str(d['holds']):>6}"
              + ("" if alpha in PRIMARY_ALPHAS else "   [exploratory]"))
    return out


def concentration(cases: list[dict]) -> list[dict]:
    """E3 and E8: is there a concentration, and is it the same band?"""
    print("\n  E3/E8 — where the pooled rule spends its budget")
    print("  " + "-" * 76)
    shares = population_shares(cases)
    opens = undetermined_share(cases)
    print(f"  {'band':>16} {'pop share':>10} {'states open':>12}")
    for b, s in shares.items():
        print(f"  {b:>16} {s:>10.1%} {opens.get(b, 0.0):>12.1%}")

    out = []
    for alpha in ALPHAS:
        bd = Breakdown(alpha=alpha)
        validate(cases, handcrafted_scorer, alpha=alpha, trials=TRIALS,
                 seed=SEED, calibration_share=CALIBRATION_SHARE,
                 on_trial=collector(bd))
        d = bd.as_dict()
        out.append(d)
        worst = max(d["concentration"].values(), default=0.0)
        print(f"\n  alpha = {alpha:.2f}   pooled {bd.pooled_unsafe_rate:.1%}"
              f"   worst band {bd.worst_band}"
              f"   max concentration {worst:.2f}"
              f"   hides a subgroup: {bd.hides_a_subgroup}")
        print(f"  {'band':>16} {'deployed':>9} {'unsafe':>7} {'rate':>7} "
              f"{'cov':>7} {'conc':>7}")
        for row in d["bands"]:
            print(f"  {row['band']:>16} {row['deployed']:>9} "
                  f"{row['unsafe']:>7} {row['unsafe_rate']:>6.1%} "
                  f"{row['coverage']:>6.1%} "
                  f"{d['concentration'][row['band']]:>7.2f}")
    return out


def schemes(cases: list[dict]) -> list[dict]:
    """E4-E7: does group conditioning fix it, and what does it cost?"""
    print("\n  E4/E5/E6/E7 — grouping schemes, paired on identical draws")
    print("  " + "-" * 76)
    print(f"  {'alpha':>6} {'scheme':>20} {'feas':>6} {'viol|feas':>10} "
          f"{'grp-viol':>9} {'worst':>7} {'cov':>7} {'conc':>6} {'q':>6}")

    out = []
    for alpha in ALPHAS:
        for name in ("pooled", "by-band", "separate-well-below"):
            v = validate_groups(cases, handcrafted_scorer, scheme=name,
                                alpha=alpha, trials=TRIALS, seed=SEED,
                                calibration_share=CALIBRATION_SHARE)
            d = v.as_dict() | {"powered": alpha in PRIMARY_ALPHAS}
            out.append(d)
            tag = "  [post-hoc]" if d["post_hoc"] else ""
            print(f"  {alpha:>6.2f} {name:>20} {d['feasible_trials']:>6} "
                  f"{fmt(d['violation_rate_when_feasible']):>10} "
                  f"{fmt(d['group_violation_rate_when_feasible']):>9} "
                  f"{d['mean_worst_group_rate']:>6.1%} "
                  f"{d['mean_coverage']:>6.1%} "
                  f"{d['mean_max_concentration']:>6.2f} "
                  f"{d['mean_questions']:>6.2f}{tag}")
        print()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=("dev", "holdout"), default="dev")
    args = ap.parse_args()

    name = f"fine_{args.set}"
    cases = json.loads((ROOT / "evidence" / f"{name}.json").read_text())

    print(f"  {name}: {len(cases)} cases")
    print(f"  {TRIALS} trials, calibration share {CALIBRATION_SHARE}, "
          f"seed {SEED}, delta 0.05")
    print(f"  schemes: {', '.join(SCHEMES)}")
    for alpha in ALPHAS:
        s = shortfall(len(cases), alpha, smallest_group_share=0.143,
                      calibration_share=CALIBRATION_SHARE)
        flag = "powered" if s["adequate"] else \
            f"UNDERPOWERED by {s['factor_short']}x"
        print(f"    alpha {alpha:.2f}: needs {s['needed']:>5} cases — {flag}")

    t0 = time.time()
    payload = {
        "set": name, "n_cases": len(cases), "trials": TRIALS,
        "calibration_share": CALIBRATION_SHARE, "seed": SEED,
        "primary_alphas": list(PRIMARY_ALPHAS),
        "exploratory_alphas": list(EXPLORATORY_ALPHAS),
        "E1_E2_replication": replication(cases),
        "E3_E8_concentration": concentration(cases),
        "E4_E7_schemes": schemes(cases),
    }
    payload["elapsed_seconds"] = round(time.time() - t0, 1)

    dest = ROOT / "evidence" / f"round4_{args.set}.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
