#!/usr/bin/env python3
"""
Why the lowest-income band absorbs the error budget.

The write-up says "score levels are shifted between bands", which is true and
is not a mechanism. This locates the cause, and rules out the alternative I
expected to find.

The hypothesis I expected, and rejected
---------------------------------------
Determinability here fires on two conditions: the eligibility verdict flips
across the sweep, **or** the benefit amount moves by more than the materiality
threshold while the verdict is stable. The obvious story was that
`well-below` is dominated by the second — households clearly eligible on
income, whose benefit *amount* still swings with household size — and that the
scorer, which measures distance from the *eligibility* boundary, is blind to
it by construction.

Reconstructed from the complete enumeration (no oracle calls: every swept
household is itself in the benchmark, so its verdict can be looked up), the
shares of undetermined states that are amount-only are

    well-below 31% · near-threshold 42% · above 15% · well-above 14%

`well-below` is not dominated by amount-only undeterminacy, and the band with
the most of it is the one that takes **none** of the budget. The story is
wrong and is recorded here rather than quietly dropped.

What is actually happening
--------------------------
The scorer's one real feature is distance from the eligibility boundary. For
households far **below** the income limit that distance is maximal, so the
scorer is maximally confident — while eligibility still flips for 69% of their
undetermined states, because household size moves both the limit and the
award.

So the failure is not that the scorer ranks badly. It is that its structural
assumption — far from the boundary implies determinable — is **false in one
direction**, and false consistently rather than noisily. A single global
threshold cannot correct a bias that is consistent within a group and
different between groups; a per-group threshold can, because inside a band the
feature's relationship to determinability is at least stable.

Which generalises past this benchmark: a confidence feature encoding "far from
the decision boundary along dimension X" is systematically overconfident on
exactly the cases where a different dimension decides.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import BANDS, hardness  # noqa: E402
from abstain.scorer import FIELDS, features, handcrafted_scorer  # noqa: E402
from abstain.validate import states_of  # noqa: E402

SWEEPABLE = {
    "dependents": [0, 1, 2, 3],
    "employment_income": [0, 9_000, 18_000, 27_000, 36_000],
    "age": [22, 35, 50, 64],
    "state_name": ["NY", "TX", "CA", "MS"],
}


def criterion_split(full_space: list[dict]) -> dict:
    """
    Per band, how many undetermined states flip eligibility rather than only
    moving the amount.

    Every swept household is in the complete enumeration, so its
    full-information verdict is a lookup rather than an engine call.
    """
    verdict = {tuple(c["household"][f] for f in FIELDS):
               c["states"]["|".join(sorted(FIELDS))]["truth"]
               for c in full_space}

    out: dict[str, dict] = {b: {"flip": 0, "amount_only": 0} for b in BANDS}
    for case in full_space:
        hh = case["household"]
        band = hardness(case)
        for r in range(len(FIELDS) + 1):
            for known in itertools.combinations(FIELDS, r):
                if case["states"]["|".join(sorted(known))]["label"] != \
                        "underdetermined":
                    continue
                unknown = [f for f in FIELDS if f not in known]
                seen = set()
                for combo in itertools.product(
                        *[SWEEPABLE[f] for f in unknown]):
                    trial = dict(hh)
                    trial.update(dict(zip(unknown, combo)))
                    seen.add(verdict[tuple(trial[f] for f in FIELDS)])
                key = "flip" if len(seen) > 1 else "amount_only"
                out[band][key] += 1
    return out


def score_profile(cases: list[dict]) -> dict:
    """
    Per band, what the scorer says about states that are undetermined.

    Restricted to states where income is known, because income unknown scores
    zero by construction in every band and would wash out the comparison.
    """
    rows = states_of(cases)
    out: dict[str, dict] = {}
    for band in BANDS:
        sub = [(c, k) for c, k, det in rows
               if hardness(c) == band and not det
               and "employment_income" in k]
        if not sub:
            continue
        scores = sorted(handcrafted_scorer(c, k) for c, k in sub)
        out[band] = {
            "undetermined_states": len(sub),
            "share_scoring_zero": sum(1 for s in scores if s == 0.0)
            / len(sub),
            "median_score": scores[len(scores) // 2],
            "mean_score": sum(scores) / len(scores),
            "mean_log_distance": sum(features(c, k)["log_distance"]
                                     for c, k in sub) / len(sub),
        }
    return out


def main() -> int:
    full = json.loads((ROOT / "evidence" / "cases_fine.json").read_text())
    dev = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())

    print("  The hypothesis that was wrong")
    print("  " + "-" * 70)
    print("  If well-below failed because the benefit AMOUNT moves while")
    print("  eligibility is settled, it would be mostly amount-only.\n")
    crit = criterion_split(full)
    print(f"  {'band':>16} {'undetermined':>13} {'elig flips':>11} "
          f"{'amount only':>12}")
    for b in BANDS:
        d = crit[b]
        tot = d["flip"] + d["amount_only"]
        print(f"  {b:>16} {tot:>13} {d['flip']:>11} "
              f"{d['amount_only']:>7} ({d['amount_only'] / tot:>3.0%})")
    print("\n  It is not. near-threshold has the largest amount-only share")
    print("  and takes none of the budget. Hypothesis rejected.\n")

    print("  What the scorer actually does")
    print("  " + "-" * 70)
    prof = score_profile(dev)
    print(f"  {'band':>16} {'undet states':>13} {'score==0':>9} "
          f"{'median':>8} {'mean dist':>10}")
    for b in BANDS:
        if b not in prof:
            continue
        d = prof[b]
        print(f"  {b:>16} {d['undetermined_states']:>13} "
              f"{d['share_scoring_zero']:>8.0%} {d['median_score']:>8.4f} "
              f"{d['mean_log_distance']:>10.4f}")

    wb = crit["well-below"]
    flip_share = wb["flip"] / (wb["flip"] + wb["amount_only"])
    print("\n  Not one undetermined well-below state scores zero, and their")
    print("  median score is the highest of any band. The scorer's one real")
    print("  feature is distance from the eligibility boundary, which is")
    print("  maximal for households far BELOW the limit -- while eligibility")
    print(f"  still flips for {flip_share:.0%} of their undetermined states.")

    payload = {"criterion_split": crit, "score_profile": prof,
               "hypothesis_rejected": "amount-only undeterminacy does not "
                                      "explain the well-below failure"}
    dest = ROOT / "evidence" / "mechanism.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
