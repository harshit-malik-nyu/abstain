#!/usr/bin/env python3
"""
Is the fix "calibrate per group", or just "recalibrate often"?

Round five held calibration at the natural mix however far deployment moved.
That models the onset of a shift and leaves the result open to a one-line
rebuttal: of course the pooled rule fails, it was never allowed to
recalibrate. The addendum in `docs/preregistration-5.md` registers G1–G3
before this file existed; this runs them.

The comparison is the same sweep twice, paired per trial:

    stale          calibration stays at the natural mix (round five)
    recalibrated   calibration is reweighted to the deployment mix

If recalibration alone restores both validity **and** an even error budget,
the recommendation from this repository is the easier and more standard one —
recalibrate when your population moves — and the group-conditional argument is
substantially weaker than stated. That would be reported at the top of the
README rather than here.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.shift import sweep_shift  # noqa: E402

SHARES = (0.143, 0.25, 0.40, 0.60, 0.80, 1.00)
ALPHA = 0.20
TRIALS = 300
SEED = 41
CALIBRATION_SHARE = 0.30


def fmt(x) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}, "
          f"alpha {ALPHA}")

    t0 = time.time()
    sweeps = {}
    for label, recal in (("stale", False), ("recalibrated", True)):
        sweeps[label] = sweep_shift(
            cases, handcrafted_scorer, band="well-below", shares=SHARES,
            schemes=("pooled", "by-band"), alphas=(ALPHA,), trials=TRIALS,
            seed=SEED, calibration_share=CALIBRATION_SHARE,
            shift_calibration=recal)
        print(f"  {label}: {time.time() - t0:.0f}s elapsed")

    def point(label: str, scheme: str, share: float):
        return next(p for p in sweeps[label].points
                    if p.scheme == scheme and p.target_share == share)

    print("\n  G1 — does recalibration restore validity?")
    print(f"  {'wb share':>9} {'stale pooled':>13} "
          f"{'recalibrated pooled':>20}")
    for s in SHARES:
        print(f"  {s:>9.3f} {fmt(point('stale', 'pooled', s).violation_rate):>13} "
              f"{fmt(point('recalibrated', 'pooled', s).violation_rate):>20}")

    print("\n  G2 — what is group conditioning still worth after "
          "recalibration?")
    print(f"  {'wb share':>9} {'pooled cov':>11} {'by-band cov':>12} "
          f"{'advantage':>10}")
    for s in SHARES:
        p = point("recalibrated", "pooled", s)
        b = point("recalibrated", "by-band", s)
        print(f"  {s:>9.3f} {p._mean(p.coverage_sum):>10.1%} "
              f"{b._mean(b.coverage_sum):>11.1%} "
              f"{b._mean(b.coverage_sum) - p._mean(p.coverage_sum):>+10.1%}")

    print("\n  G3 — does a recalibrated pooled rule still concentrate?")
    print(f"  {'wb share':>9} {'pooled rate':>12} {'worst band':>11} "
          f"{'conc':>7} {'hides a subgroup':>17}")
    for s in SHARES:
        p = point("recalibrated", "pooled", s)
        d = p.as_dict()
        print(f"  {s:>9.3f} {d['mean_unsafe_rate']:>11.1%} "
              f"{d['worst_band_rate']:>10.1%} "
              f"{d['max_concentration']:>7.2f} "
              f"{str(d['hides_a_subgroup']):>17}")

    payload = {"set": "fine_dev", "alpha": ALPHA, "trials": TRIALS,
               "seed": SEED, "calibration_share": CALIBRATION_SHARE,
               "stale": sweeps["stale"].as_dict(),
               "recalibrated": sweeps["recalibrated"].as_dict(),
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "recalibration.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
