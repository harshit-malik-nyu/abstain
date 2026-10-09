#!/usr/bin/env python3
"""
At what calibration size does the correction stop earning its keep?

`docs/preregistration-5.md`, addendum four, committed before this file.

Round two justified the Clopper–Pearson bound by beating a plug-in threshold
on 79 cases with a 40–50 case calibration fold. That comparison is the answer
to "why not just pick a threshold?" and the reason the bound is in the method,
and it has never been run anywhere else.

The correction it justifies is a **finite-sample** correction. The empirical
rate converges as n grows and the gap to an upper bound shrinks with it, so
the comparison plausibly dissolves at scale — in which case the honest claim
is "below some n", and the useful output is that n.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

SIZES = (25, 50, 100, 200, 400)
ALPHAS = (0.20, 0.10)
TRIALS = 300
SEED = 61
DELTA = 0.05


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}, "
          f"delta {DELTA}")
    print("  round two ran this on 79 cases with a 40-50 case fold\n")

    t0 = time.time()
    rows = []
    for alpha in ALPHAS:
        print(f"  alpha = {alpha:.2f}")
        print(f"  {'n_cal':>6} {'bound':>16} {'feas':>6} {'viol|feas':>10} "
              f"{'infeas':>7} {'cov':>7} {'holds delta':>12}")
        for n_cal in SIZES:
            for bound in ("clopper-pearson", "plugin"):
                v = validate(cases, handcrafted_scorer, alpha=alpha,
                             delta=DELTA, trials=TRIALS, seed=SEED,
                             bound=bound, calibration_size=n_cal)
                d = v.as_dict() | {"calibration_size": n_cal, "bound": bound}
                rows.append(d)
                vf = d["violation_rate_when_feasible"]
                print(f"  {n_cal:>6} {bound:>16} {d['feasible_trials']:>6} "
                      f"{fmt(vf):>10} {d['infeasible_rate']:>6.1%} "
                      f"{d['mean_coverage']:>6.1%} "
                      f"{str(d['holds']):>12}")
            print()

    print("  Where does the correction stop mattering?")
    print("  " + "-" * 62)
    for alpha in ALPHAS:
        crossover = None
        for n_cal in SIZES:
            plug = next(r for r in rows if r["alpha"] == alpha
                        and r["calibration_size"] == n_cal
                        and r["bound"] == "plugin")
            rate = plug["violation_rate_when_feasible"]
            if rate is not None and rate <= DELTA and crossover is None:
                crossover = n_cal
        if crossover:
            print(f"  alpha={alpha:.2f}: the plug-in first holds delta at "
                  f"{crossover} calibration cases")
        else:
            print(f"  alpha={alpha:.2f}: the plug-in never holds delta, up "
                  f"to {max(SIZES)} calibration cases")

    payload = {"set": "fine_dev", "trials": TRIALS, "seed": SEED,
               "delta": DELTA, "sizes": list(SIZES), "rows": rows,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "plugin_scale.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
