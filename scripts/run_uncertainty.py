#!/usr/bin/env python3
"""
How certain is any of this?

Every per-band figure in this repository pools deployed cases across hundreds
of trials, and the same case appears in most of them: on the holdout, 96
distinct `well-below` cases produce 26,752 observations. A standard error
computed from 26,752 would claim about ±0.6 points on a figure whose real
support is 96 households.

That interval is not merely optimistic. It answers a different question — how
precisely the rate is known *for these 96 households* — when the claim being
made is about households like them.

So the headline per-band rates get a **cluster bootstrap over cases**, and the
naive interval is reported beside it so the gap is visible rather than
asserted. Nothing here is novel; what would have been novel is reporting the
naive one.

This recomputes rather than re-reads, because the per-case structure was not
recorded when rounds four and five ran. Same set, seed, trial count and
calibration share, so the point estimates reproduce the published ones — and
the script checks that they do, since a bootstrap around a different point
estimate would be measuring a different experiment.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import (Breakdown, bootstrap_all_bands,  # noqa: E402
                                 collector)
from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

ALPHAS = (0.20, 0.15)
TRIALS = 400
SEED = 31
CALIBRATION_SHARE = 0.30
DRAWS = 5_000


def published(alpha: float, which: str) -> dict | None:
    path = ROOT / "evidence" / f"round4_{which}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    return next((c for c in payload["E3_E8_concentration"]
                 if c["alpha"] == alpha), None)


def main() -> int:
    t0 = time.time()
    out = []

    for which in ("dev", "holdout"):
        cases = json.loads(
            (ROOT / "evidence" / f"fine_{which}.json").read_text())
        print(f"\n  fine_{which}: {len(cases)} cases, {TRIALS} trials, "
              f"seed {SEED}")

        for alpha in ALPHAS:
            bd = Breakdown(alpha=alpha)
            validate(cases, handcrafted_scorer, alpha=alpha, trials=TRIALS,
                     seed=SEED, calibration_share=CALIBRATION_SHARE,
                     on_trial=collector(bd))

            # The point estimates must match what was published, or the
            # bootstrap is wrapping an interval around a different run.
            ref = published(alpha, which)
            if ref:
                for row in bd.as_dict()["bands"]:
                    was = next(b["unsafe_rate"] for b in ref["bands"]
                               if b["band"] == row["band"])
                    assert abs(was - row["unsafe_rate"]) < 1e-9, (
                        f"{which} alpha={alpha} {row['band']}: recomputed "
                        f"{row['unsafe_rate']} against published {was}")

            rows = bootstrap_all_bands(bd.per_case, draws=DRAWS)
            for r in rows:
                r |= {"set": which, "alpha": alpha}
            out.extend(rows)

            print(f"\n  alpha = {alpha:.2f}"
                  + ("   (point estimates match the published run)"
                     if ref else ""))
            print(f"  {'band':>16} {'cases':>6} {'obs':>7} {'rate':>7} "
                  f"{'95% CI (cluster)':>20} {'naive ±':>9} "
                  f"{'cluster ±':>10}")
            for r in rows:
                ci = f"[{r['lo']:.1%}, {r['hi']:.1%}]"
                print(f"  {r['band']:>16} {r['cases']:>6} "
                      f"{r['observations']:>7} {r['point']:>6.1%} "
                      f"{ci:>20} {r['naive_halfwidth']:>8.1%} "
                      f"{r['clustered_halfwidth']:>9.1%}")

    print("\n  Does the uncertainty change any conclusion?")
    print("  " + "-" * 68)
    for r in out:
        if r["band"] != "well-below":
            continue
        verdict = ("still above the budget"
                   if r["lo"] > r["alpha"] else
                   "NOT clearly above the budget")
        print(f"  {r['set']:>8} alpha={r['alpha']:.2f}  "
              f"lower bound {r['lo']:.1%} vs tolerance {r['alpha']:.0%}  "
              f"-> {verdict}")

    payload = {"trials": TRIALS, "seed": SEED, "draws": DRAWS,
               "calibration_share": CALIBRATION_SHARE, "rows": out,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "uncertainty.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
