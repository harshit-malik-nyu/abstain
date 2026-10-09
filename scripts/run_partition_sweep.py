#!/usr/bin/env python3
"""
Round Q — is the subgroup finding a property of the method or of the partition?

`docs/preregistration-5.md`, addendum nine, committed before this file and
before `collector` accepted a `partition`. Q1–Q7 and every cutoff below are
fixed there and none is added, dropped or adjusted after a result.

Why this round exists
---------------------
The headline finding is stated *per band*: `well-below` absorbs 4.12x its
share of the error budget. `well-below` is `income <= 6_000`, which on this
benchmark's income grid is three values out of twenty-one — 96 of 672 cases —
and the three cutoffs were written by hand in `scripts/split.py`.

Round five swept the other hand-chosen constant, materiality, from $0 to $500
and found the concentration unmoved. The partition has never been swept, and
it is the more dangerous of the two because the finding is phrased in its
terms. `split.py` is the first commit in the repository, so the cutoffs cannot
have been tuned to the result — which rules out tuning, not luck.

How the comparison is kept honest
---------------------------------
Every partition is tallied over the **same trajectories**, from one `validate`
pass per tolerance with several collectors attached. A second run per
partition would differ for reasons having nothing to do with the grouping;
this way the only thing that varies is the grouping.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import (BANDS, Breakdown,  # noqa: E402
                                 collector, population_shares)
from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

ALPHAS = (0.20, 0.15)
TRIALS = 200
SEED = 53
CALIBRATION_SHARE = 0.30

# Every cutoff here is fixed in addendum nine.
NEUTRAL_QUARTILES = (15_000, 30_000, 45_000)   # equal-count on this benchmark
BOTTOM_CUTOFFS = (3_000, 6_000, 9_000, 12_000, 15_000)
MEDIAN = 30_000
EIGHT = (6_000, 12_000, 18_000, 24_000, 30_000, 36_000, 48_000)


def cuts_partition(cuts: tuple[int, ...], names: tuple[str, ...]):
    """A partition of income into len(cuts)+1 contiguous bands."""
    assert len(names) == len(cuts) + 1, (names, cuts)

    def part(case: dict) -> str:
        income = case["household"]["employment_income"]
        for name, edge in zip(names, cuts):
            if income <= edge:
                return name
        return names[-1]

    part.cuts = cuts          # type: ignore[attr-defined]
    part.names = names        # type: ignore[attr-defined]
    return part


def bottom_cutoff_partition(edge: int):
    """
    `well-below` redefined at `edge`, the upper cutoffs left where they are.

    Asks how far up the income range the effect reaches. The band is named
    for its cutoff so a reader cannot confuse it with the published
    `well-below`.
    """
    names = (f"bottom<={edge // 1000}k", "near-threshold", "above",
             "well-above")
    cuts = (edge, 24_000, 36_000)
    if edge >= 24_000:                       # not reachable with the fixed set
        raise ValueError(edge)
    return cuts_partition(cuts, names)


def build_partitions() -> dict[str, object]:
    """Every partition in the sweep, keyed by the name used in the output."""
    out: dict[str, object] = {}

    published = cuts_partition((6_000, 24_000, 36_000), BANDS)
    out["published"] = published

    out["equal-count-quartiles"] = cuts_partition(
        NEUTRAL_QUARTILES, ("q1-poorest", "q2", "q3", "q4-richest"))

    for edge in BOTTOM_CUTOFFS:
        out[f"bottom-at-{edge // 1000}k"] = bottom_cutoff_partition(edge)

    out["two-bands-at-median"] = cuts_partition(
        (MEDIAN,), ("below-median", "above-median"))

    out["eight-bands"] = cuts_partition(
        EIGHT, tuple(f"b{i}" for i in range(len(EIGHT) + 1)))

    return out


def run(cases: list[dict], alpha: float,
        partitions: dict[str, object]) -> dict[str, dict]:
    """
    One deployment pass, every partition tallied from it.

    `validate` takes a single `on_trial`, so the collectors are fanned out by
    a wrapper. That is the whole trick that makes this a partition comparison
    rather than a comparison of runs.
    """
    breakdowns = {}
    callbacks = []
    for name, part in partitions.items():
        bd = Breakdown(alpha=alpha,
                       order=tuple(part.names))  # type: ignore[attr-defined]
        breakdowns[name] = bd
        callbacks.append(collector(bd, partition=part))

    def fan_out(cal, result, dep_cases):
        for cb in callbacks:
            cb(cal, result, dep_cases)

    v = validate(cases, handcrafted_scorer, alpha=alpha, trials=TRIALS,
                 seed=SEED, calibration_share=CALIBRATION_SHARE,
                 on_trial=fan_out)

    out = {}
    for name, bd in breakdowns.items():
        part = partitions[name]
        d = bd.as_dict()
        d["shares"] = population_shares(cases, partition=part)
        d["cuts"] = list(part.cuts)        # type: ignore[attr-defined]
        d["mean_coverage"] = v.mean_coverage
        d["violation_rate_when_feasible"] = v.violation_rate_when_feasible
        out[name] = d

        worst = d["worst_band"]
        conc = d["concentration"].get(worst, 0.0) if worst else 0.0
        rate = next((b["unsafe_rate"] for b in d["bands"]
                     if b["band"] == worst), 0.0)
        print(f"  {name:>22}  bands {len(d['bands']):>2}  worst "
              f"{str(worst):>14} at {rate:>6.2%}  conc {conc:>5.2f}  "
              f"hides {'yes' if d['hides_a_subgroup'] else 'no':>3}")
    return out


def score(at20: dict[str, dict]) -> dict:
    """Q1-Q7 against addendum nine, which fixes every threshold used."""
    pub = at20["published"]
    neutral = at20["equal-count-quartiles"]
    two = at20["two-bands-at-median"]
    eight = at20["eight-bands"]

    def conc(d: dict) -> float:
        w = d["worst_band"]
        return d["concentration"].get(w, 0.0) if w else 0.0

    bottoms = [(e, at20[f"bottom-at-{e // 1000}k"]) for e in BOTTOM_CUTOFFS]
    bottom_conc = [(e, conc(d)) for e, d in bottoms]
    falling = all(b >= a for (_, b), (_, a)
                  in zip(bottom_conc, bottom_conc[1:]))

    at3 = dict(bottom_conc)[3_000]
    pub_conc = conc(pub)

    out = {
        "Q1": {"claim": "a band still exceeds alpha under equal-count "
                        "quartiles",
               "hides": neutral["hides_a_subgroup"],
               "held": neutral["hides_a_subgroup"]},
        "Q2": {"claim": "the worst quartile is the poorest",
               "worst": neutral["worst_band"],
               "held": neutral["worst_band"] == "q1-poorest"},
        "Q3": {"claim": "its concentration is above 2.0",
               "value": conc(neutral),
               "held": conc(neutral) > 2.0},
        "Q4": {"claim": "concentration falls monotonically as the bottom "
                        "cutoff rises",
               "series": bottom_conc, "held": falling},
        "Q5": {"claim": "a 3k cutoff concentrates more than the published 6k",
               "at_3k": at3, "published": pub_conc, "held": at3 > pub_conc},
        "Q6": {"claim": "two bands at the median show concentration below 2.0",
               "value": conc(two), "hides": two["hides_a_subgroup"],
               "held": conc(two) < 2.0},
        "Q7": {"claim": "eight bands localise further than four",
               "value": conc(eight), "published": pub_conc,
               "held": conc(eight) > pub_conc},
    }
    print("\n  Q1-Q7, scored against addendum nine")
    for k, v in out.items():
        print(f"  {k}  {'held' if v['held'] else 'MISSED':>6}   {v['claim']}")
    return out


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    partitions = build_partitions()
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}")
    print(f"  {len(partitions)} partitions tallied from the same "
          f"trajectories\n")

    t0 = time.time()
    results = {}
    for alpha in ALPHAS:
        print(f"  alpha = {alpha:.2f}")
        results[f"{alpha:.2f}"] = run(cases, alpha, partitions)
        print()

    scored = score(results[f"{ALPHAS[0]:.2f}"])

    payload = {"set": "fine_dev", "trials": TRIALS, "seed": SEED,
               "calibration_share": CALIBRATION_SHARE,
               "partitions": {k: list(v.cuts)   # type: ignore[attr-defined]
                              for k, v in partitions.items()},
               "by_alpha": results,
               "predictions": scored,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "partition_sweep.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
