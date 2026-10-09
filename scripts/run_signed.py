#!/usr/bin/env python3
"""
Round N — does the *sign* of the distance fix what its magnitude could not?

`docs/preregistration-5.md`, addendum seven, committed before this script
existed. N1–N4 and the analysis plan are fixed there: `fine_dev`, 200 trials,
seed 89, α = 0.20 and 0.15, weight 0.8 carried over unchanged from addendum
six. Neither holdout is touched and nothing below is adjusted after a result.

Why the round exists
--------------------
`award_aware_scorer` (round M) produced results identical to the handcrafted
scorer in every digit, and M1 — the mechanism's own prediction — failed. Two
explanations followed. The first, that the new term is a monotone transform,
was published and then **retracted**: the sample behind it covered one band.
The second is that the term fires only while `dependents` is unknown and the
greedy selector asks for `dependents` first in every case that asks anything,
so the term acts on the opening state and nowhere else.

`signed_scorer` is the one change that escapes that argument on paper: it
applies the penalty only *below* the boundary, so it reorders states rather
than rescaling them. N1 was scored before this run — 2.78% of reachable pairs
flip — and recorded as **the wrong guard**, because reordering was never the
thing that was broken. This run scores N2–N4, which are about whether the
reordering reaches the deployed rule.

The honest prior, written here before the run: the term still switches off at
the agent's first question, so N2 is expected to fail for the same reason M1
did. Recording that expectation is not the same as pre-registering it — the
pre-registration is addendum seven and it says N2 will hold.
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import Breakdown, collector  # noqa: E402
from abstain.group import validate_groups  # noqa: E402
from abstain.evaluate import OPENING  # noqa: E402
from abstain.scorer import (auc, award_aware_scorer,  # noqa: E402
                            handcrafted_scorer, signed_scorer)
from abstain.validate import states_of, validate  # noqa: E402

ALPHAS = (0.20, 0.15)
TRIALS = 200
SEED = 89                     # fixed in addendum seven's analysis plan
CALIBRATION_SHARE = 0.30
FLIP_PAIRS = 100_000
FLIP_SEED = 89

SCORERS = (("handcrafted", handcrafted_scorer),
           ("award-aware", award_aware_scorer),
           ("signed", signed_scorer))


def reachable_states(cases: list[dict]) -> list[tuple[dict, frozenset[str]]]:
    """
    The states the rule can actually occupy.

    The opening state knows income and the rule only ever adds fields, so a
    state without income is unreachable. Measuring order flips over *all*
    states is what produced the retracted claim — not because the filter was
    missing, but because the sample was taken in case order. Both are fixed
    here: the filter, and a random sample rather than a prefix.
    """
    return [(c, k) for c, k, _ in states_of(cases)
            if OPENING <= k]


def flip_rate(cases: list[dict], a, b, *, label: str) -> dict:
    """
    N1's measurement: how often `a` and `b` order a pair of states differently.

    Sampled uniformly over *pairs* of reachable states with a fixed seed, so
    the number is reproducible and does not depend on iteration order. The
    retracted version took `states_of(cases)[:700]`, which covered the first
    ~44 cases and therefore one band.
    """
    pool = reachable_states(cases)
    rng = random.Random(FLIP_SEED)
    flips = ties = 0
    n = 0
    for _ in range(FLIP_PAIRS):
        (c1, k1), (c2, k2) = rng.choice(pool), rng.choice(pool)
        x1, x2 = a(c1, k1), a(c2, k2)
        y1, y2 = b(c1, k1), b(c2, k2)
        if x1 == x2 or y1 == y2:
            ties += 1
            continue
        n += 1
        if (x1 > x2) != (y1 > y2):
            flips += 1
    rate = flips / n if n else 0.0
    print(f"  {label}: {rate:.2%} of {n:,} comparable reachable pairs reorder "
          f"({ties:,} tied)")
    return {"pairs_sampled": FLIP_PAIRS, "comparable": n, "ties": ties,
            "flips": flips, "flip_rate": rate, "seed": FLIP_SEED,
            "population": "reachable states, uniform over pairs"}


def measure(cases: list[dict], label: str, scorer) -> list[dict]:
    rows = states_of(cases)
    a = auc([(scorer(c, k), d) for c, k, d in rows])

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
        print(f"\n  {label}, alpha = {alpha:.2f}   AUC {a:.4f}   pooled "
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
    """What is left for group conditioning once the sign is in the score?"""
    print("\n  group conditioning on top")
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


def score(arms: dict, flips: dict) -> dict:
    """
    N1-N4 against the numbers in addendum seven, which are fixed there.

    Written as data rather than prose so `tests/` can check that the ledger
    in `docs/predictions.md` says what the run says.
    """
    hand = next(r for r in arms["handcrafted"] if r["alpha"] == 0.20)
    sign = next(r for r in arms["signed"] if r["alpha"] == 0.20)

    conc = sign["concentration"][sign["worst_band"]]
    wb_hand = next(b for b in hand["bands"] if b["band"] == "well-above")
    wb_sign = next(b for b in sign["bands"] if b["band"] == "well-above")
    rise = wb_sign["unsafe_rate"] - wb_hand["unsafe_rate"]

    out = {
        "N1": {"claim": ">1% of reachable state pairs flip vs handcrafted",
               "value": flips["signed_vs_handcrafted"]["flip_rate"],
               "held": flips["signed_vs_handcrafted"]["flip_rate"] > 0.01},
        "N2": {"claim": "well-below concentration below 2.5, from 4.07",
               "value": conc,
               "worst_band": sign["worst_band"],
               "held": sign["worst_band"] == "well-below" and conc < 2.5},
        "N3": {"claim": "well-above unsafe rate rises by at most 3 points",
               "value": rise, "held": rise <= 0.03},
        "N4": {"claim": "coverage stays above 68%",
               "value": sign["mean_coverage"],
               "held": sign["mean_coverage"] > 0.68},
    }
    print("\n  N1-N4, scored against addendum seven")
    for k, v in out.items():
        print(f"  {k}  {'held' if v['held'] else 'MISSED':>6}   "
              f"{v['value']:.4f}   {v['claim']}")
    return out


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}")
    print("  weight 0.8, carried over unchanged from addendum six")

    t0 = time.time()
    print()
    flips = {
        "signed_vs_handcrafted":
            flip_rate(cases, signed_scorer, handcrafted_scorer,
                      label="signed vs handcrafted"),
        "award_aware_vs_handcrafted":
            flip_rate(cases, award_aware_scorer, handcrafted_scorer,
                      label="award-aware vs handcrafted"),
    }

    arms = {label: measure(cases, label, scorer) for label, scorer in SCORERS}
    schemes = conditioning(cases)
    scored = score(arms, flips)

    print("\n  side by side at alpha = 0.20")
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
               "order_flips": flips,
               "arms": arms,
               "schemes": schemes,
               "predictions": scored,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "signed_scorer.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
