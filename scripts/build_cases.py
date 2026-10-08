#!/usr/bin/env python3
"""
Generate a benchmark large enough to split.

Why this comes before the split
-------------------------------
The companion benchmark has 16 cases. Split in half that is seven and nine,
and nothing measured on seven cases supports a claim about a selection rule —
the standard error on a rate at n=7 is roughly 19 points, which is wider than
every effect this project is trying to detect.

So the cases are regenerated at a size that can carry a dev and a holdout half
each large enough to measure on, and only then split.

What a case is
--------------
A household, plus the oracle's verdict for every subset of fields the agent
might know. With four fields that is sixteen knowledge states per case, each
labelled determinable or underdetermined with the answer where one exists.

The oracle is PolicyEngine, which implements the published US benefit rules.
It is used as a consistent arbiter rather than assumed correct in any absolute
sense: the same household always yields the same verdict, so determinability
is a property of the case rather than of who was asked.

Cost
----
Each state is an engine evaluation and the engine is slow. Results are cached
across states and across cases, because households sharing a field
combination share the computation — without the cache this takes hours
instead of minutes.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FIELDS = ("employment_income", "dependents", "age", "state_name")

# Ranges the agent sweeps when deciding whether a missing field could change
# the answer. Mirrors the companion benchmark so results remain comparable.
SWEEPABLE = {
    "dependents": [0, 1, 2, 3],
    "employment_income": [0, 9_000, 18_000, 27_000, 36_000],
    "age": [22, 35, 50, 64],
    "state_name": ["NY", "TX", "CA", "MS"],
}


def situation(hh: dict, year: int = 2025) -> dict:
    people = {"adult": {"age": {str(year): hh["age"]},
                        "employment_income": {str(year): hh["employment_income"]}}}
    members = ["adult"]
    for i in range(hh["dependents"]):
        people[f"child{i}"] = {"age": {str(year): 8}}
        members.append(f"child{i}")
    return {"people": people,
            "families": {"f": {"members": members}},
            "spm_units": {"s": {"members": members}},
            "tax_units": {"t": {"members": members}},
            "households": {"h": {"members": members,
                                 "state_name": {str(year): hh["state_name"]}}}}


class Oracle:
    def __init__(self):
        self.cache: dict[tuple, float] = {}
        self.calls = 0

    def benefit(self, hh: dict) -> float:
        key = tuple(hh[f] for f in FIELDS)
        if key in self.cache:
            return self.cache[key]
        from policyengine_us import Simulation
        self.calls += 1
        v = float(Simulation(situation=situation(hh)).calculate("snap", 2025)[0])
        self.cache[key] = v
        return v


def assess(hh: dict, known: tuple[str, ...], oracle: Oracle,
           material: float = 50.0) -> dict:
    """Is the case decidable knowing only `known`, and what is the answer?"""
    unknown = [f for f in FIELDS if f not in known]
    if not unknown:
        b = oracle.benefit(hh)
        return {"label": "determinable",
                "truth": "eligible" if b > 0 else "not_eligible",
                "spread": 0.0}

    outcomes, eligible = [], []
    for combo in itertools.product(*[SWEEPABLE[f] for f in unknown]):
        trial = dict(hh)
        trial.update(dict(zip(unknown, combo)))
        b = oracle.benefit(trial)
        outcomes.append(b)
        eligible.append(b > 0)

    spread = max(outcomes) - min(outcomes)
    flips = len(set(eligible)) > 1
    if flips or spread > material:
        return {"label": "underdetermined", "truth": "cannot_determine",
                "spread": round(spread, 2)}
    return {"label": "determinable",
            "truth": "eligible" if eligible[0] else "not_eligible",
            "spread": round(spread, 2)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=160)
    ap.add_argument("--seed", type=int, default=515)
    ap.add_argument("--out", default=str(ROOT / "evidence" / "cases.json"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    oracle = Oracle()
    started = time.time()

    # Income is drawn across the eligibility boundary deliberately. A benchmark
    # of households far from any threshold is decidable whatever is missing,
    # and would be passed by a rule that never abstains.
    incomes = [0, 6_000, 12_000, 18_000, 21_000, 24_000, 30_000, 36_000,
               48_000, 60_000]

    seen, cases = set(), []
    while len(cases) < args.n:
        hh = {"employment_income": rng.choice(incomes),
              "dependents": rng.choice([0, 1, 2, 3]),
              "age": rng.choice([22, 35, 50, 64]),
              "state_name": rng.choice(["NY", "TX", "CA", "MS"])}
        key = tuple(hh[f] for f in FIELDS)
        if key in seen:
            continue
        seen.add(key)

        states = {}
        for r in range(len(FIELDS) + 1):
            for known in itertools.combinations(FIELDS, r):
                states["|".join(sorted(known))] = assess(hh, known, oracle)

        cases.append({"id": len(cases), "household": hh, "states": states})
        if len(cases) % 20 == 0:
            print(f"  {len(cases)}/{args.n}  ({oracle.calls} engine calls, "
                  f"{time.time()-started:.0f}s)", flush=True)

    Path(args.out).write_text(json.dumps(cases, separators=(",", ":")))
    print(f"\n  {len(cases)} cases, {oracle.calls} engine calls, "
          f"{time.time()-started:.0f}s")
    print(f"  cache hits saved {len(cases) * 2 ** len(FIELDS) - oracle.calls:,} "
          "evaluations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
