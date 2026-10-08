#!/usr/bin/env python3
"""
Questions per case, per band, under each grouping scheme.

Why this is its own script
--------------------------
The claim it measures is the project's central mechanistic one: *a single
global threshold mis-allocates questions, not just risk.* It was first
inferred from safety and coverage moving together, then measured in an ad-hoc
120-trial run whose numbers went into the README with no evidence file behind
them.

`tests/test_writeup_matches_evidence.py` caught that, which is what it is for.
A figure quoted in prose with no recorded run behind it is the failure mode
that test exists to prevent, and the fix is to record the run rather than to
relax the test.

Same set, seed, trial count and calibration share as round four, so the
figures are comparable with everything else reported on `fine_dev`.
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

TRIALS = 400
SEED = 31
CALIBRATION_SHARE = 0.30
ALPHAS = (0.20, 0.15)
BANDS = ("well-below", "near-threshold", "above", "well-above")


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}")

    t0 = time.time()
    runs = []
    for alpha in ALPHAS:
        rows = {}
        for scheme in ("pooled", "by-band"):
            v = validate_groups(cases, handcrafted_scorer, scheme=scheme,
                                alpha=alpha, trials=TRIALS, seed=SEED,
                                calibration_share=CALIBRATION_SHARE)
            d = v.as_dict()
            runs.append(d)
            rows[scheme] = {r["band"]: r for r in d["bands"]}

        print(f"\n  alpha = {alpha:.2f} — questions per case, and the rate "
              f"each band is asked to carry")
        print(f"  {'band':>16} {'unsafe':>8} {'Q pooled':>10} "
              f"{'Q by-band':>11} {'delta':>8}")
        for b in BANDS:
            p = rows["pooled"].get(b)
            q = rows["by-band"].get(b)
            if not p or not q:
                continue
            print(f"  {b:>16} {p['unsafe_rate']:>7.1%} "
                  f"{p['questions_per_case']:>10.2f} "
                  f"{q['questions_per_case']:>11.2f} "
                  f"{q['questions_per_case'] - p['questions_per_case']:>+8.2f}")

        tot_p = sum(rows["pooled"][b]["questions_per_case"]
                    * rows["pooled"][b]["deployed"] for b in BANDS
                    if b in rows["pooled"])
        n_p = sum(rows["pooled"][b]["deployed"] for b in BANDS
                  if b in rows["pooled"])
        tot_q = sum(rows["by-band"][b]["questions_per_case"]
                    * rows["by-band"][b]["deployed"] for b in BANDS
                    if b in rows["by-band"])
        n_q = sum(rows["by-band"][b]["deployed"] for b in BANDS
                  if b in rows["by-band"])
        if n_p and n_q:
            print(f"  {'overall':>16} {'':>8} {tot_p / n_p:>10.2f} "
                  f"{tot_q / n_q:>11.2f} {tot_q / n_q - tot_p / n_p:>+8.2f}")

    payload = {"set": "fine_dev", "n_cases": len(cases), "trials": TRIALS,
               "seed": SEED, "calibration_share": CALIBRATION_SHARE,
               "runs": runs, "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "allocation.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
