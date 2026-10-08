#!/usr/bin/env python3
"""
Round five: price the assumption, and check the fix is a fix.

Two things, because they share a run and answer the same objection from
different sides.

**The shift sweep.** `docs/preregistration-5.md`, committed before
`src/abstain/shift.py` existed. Calibrate on the natural band mix, deploy on a
mix where `well-below`'s share is forced upward, and measure what breaking
exchangeability costs.

**Per-band coverage under each scheme.** Round four showed group conditioning
cutting the worst band's unsafe rate from 45.6% to 12.9%. That is only a fix
if the band is still *served*. A scheme that buys safety by abstaining on the
lowest-income households has moved the harm rather than reduced it, and the
pooled summary cannot tell the two apart.

Neither reads the fine holdout.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.group import validate_groups  # noqa: E402
from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.shift import natural_share, sanity_unshifted, sweep_shift  # noqa: E402

TRIALS_BANDS = 400
TRIALS_SHIFT = 300
SEED_BANDS = 31
SEED_SHIFT = 41
CALIBRATION_SHARE = 0.30
ALPHAS = (0.20, 0.15)
SHARES = (0.143, 0.25, 0.40, 0.60, 0.80, 1.00)


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def per_band(cases: list[dict]) -> list[dict]:
    """Is the band the fix protects still being served?"""
    print("\n  Per-band safety AND coverage, by scheme")
    print("  " + "-" * 76)
    print("  A scheme that fixes a band's unsafe rate by abstaining on it has")
    print("  moved the harm, not reduced it. Both numbers, per band.\n")

    out = []
    for alpha in ALPHAS:
        print(f"  alpha = {alpha:.2f}")
        print(f"  {'scheme':>20} {'band':>16} {'unsafe':>8} {'cov':>8} "
              f"{'abstain':>9}")
        for scheme in ("pooled", "by-band"):
            v = validate_groups(cases, handcrafted_scorer, scheme=scheme,
                                alpha=alpha, trials=TRIALS_BANDS,
                                seed=SEED_BANDS,
                                calibration_share=CALIBRATION_SHARE)
            d = v.as_dict()
            out.append(d)
            for row in d["bands"]:
                print(f"  {scheme:>20} {row['band']:>16} "
                      f"{row['unsafe_rate']:>7.1%} {row['coverage']:>7.1%} "
                      f"{row['abstention_rate']:>8.1%}")
            print(f"  {'':>20} {'— least-served band':>16} "
                  f"{'':>8} {d['min_band_coverage']:>7.1%}")
            print()
    return out


def shift(cases: list[dict]) -> dict:
    """F1-F5: what the assumption costs when it is false."""
    print("\n  The shift sweep — calibrate unshifted, deploy shifted")
    print("  " + "-" * 76)
    nat = natural_share(cases, "well-below")
    print(f"  natural well-below share: {nat:.1%}")

    control = sanity_unshifted(cases, handcrafted_scorer, alpha=0.20,
                               trials=50, seed=SEED_SHIFT)
    print(f"  control, ordinary path, alpha 0.20: "
          f"violations {fmt(control['violation_rate_when_feasible'])}, "
          f"coverage {control['mean_coverage']:.1%}")

    t0 = time.time()
    sweep = sweep_shift(cases, handcrafted_scorer, band="well-below",
                        shares=SHARES, schemes=("pooled", "by-band"),
                        alphas=ALPHAS, trials=TRIALS_SHIFT, seed=SEED_SHIFT,
                        calibration_share=CALIBRATION_SHARE)
    print(f"  ({time.time() - t0:.0f}s)\n")

    for alpha in ALPHAS:
        print(f"  alpha = {alpha:.2f}")
        print(f"  {'well-below share':>18} {'pooled viol':>12} "
              f"{'by-band viol':>13} {'pooled bound':>13} "
              f"{'distinct':>9}")
        for share in SHARES:
            p = next(x for x in sweep.for_scheme("pooled", alpha)
                     if x.target_share == share)
            b = next(x for x in sweep.for_scheme("by-band", alpha)
                     if x.target_share == share)
            print(f"  {share:>18.3f} {fmt(p.violation_rate):>12} "
                  f"{fmt(b.violation_rate):>13} "
                  f"{p.mean_reported_bound:>12.3f} "
                  f"{p.distinct_fraction:>8.1%}")
        print(f"  monotone in shift: pooled "
              f"{sweep.monotone('pooled', alpha)}, "
              f"by-band {sweep.monotone('by-band', alpha)}\n")

    return {"natural_share": nat, "control": control,
            "sweep": sweep.as_dict()}


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases")
    print(f"  bands: {TRIALS_BANDS} trials seed {SEED_BANDS} · "
          f"shift: {TRIALS_SHIFT} trials seed {SEED_SHIFT}")

    t0 = time.time()
    payload = {
        "set": "fine_dev", "n_cases": len(cases),
        "calibration_share": CALIBRATION_SHARE,
        "per_band": per_band(cases),
        "shift": shift(cases),
    }
    payload["elapsed_seconds"] = round(time.time() - t0, 1)

    dest = ROOT / "evidence" / "round5_shift.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
