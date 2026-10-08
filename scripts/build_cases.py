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
    ap.add_argument("--fine-incomes", action="store_true",
                    help="income every 3,000 from 0 to 60,000: 21 values "
                         "rather than 10, so the household space is 1,344 "
                         "rather than 640")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    oracle = Oracle()
    started = time.time()

    # Income is drawn across the eligibility boundary deliberately. A benchmark
    # of households far from any threshold is decidable whatever is missing,
    # and would be passed by a rule that never abstains.
    #
    # The space is finite and that turned out to matter. Ten incomes by four
    # dependent counts by four ages by four states is 640 households, so 640
    # is the largest benchmark this grid can produce — the original 160 is a
    # sample of a quarter of it.
    #
    # 640 is not enough for the question round three asked. `power.py` works
    # it out: group-conditional calibration at a 10% tolerance needs 29
    # calibration cases in the *smallest* group and about 89 deployed cases
    # there to resolve a rate against that tolerance, which comes to roughly
    # 1,113 cases. So the grid is refined rather than the sample enlarged.
    #
    # Refining income to every 3,000 gives 21 values and 1,344 households.
    # The refinement **strictly contains** the original grid — every one of
    # the ten original values is a multiple of 3,000 — so the coarse
    # benchmark is a subset of the fine space rather than a different
    # population, and the two remain comparable.
    incomes = (list(range(0, 60_001, 3_000)) if args.fine_incomes else
               [0, 6_000, 12_000, 18_000, 21_000, 24_000, 30_000, 36_000,
                48_000, 60_000])
    space = len(incomes) * 4 * 4 * 4
    if args.n > space:
        raise SystemExit(
            f"  --n {args.n} exceeds the {space} distinct households this "
            f"grid can produce; the dedupe loop would never terminate")
    print(f"  {len(incomes)} incomes, household space {space}, "
          f"building {args.n}", flush=True)

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

    # The oracle's version, recorded next to the cases it produced.
    #
    # The CI workflow installs `policyengine-us` unpinned, so the original
    # build used whichever release was current that day and did not write it
    # down. Determinability here is defined by what the engine says, which
    # makes the engine version part of the data rather than part of the
    # environment — two builds under different versions are two benchmarks,
    # and without this recorded there is no way to tell them apart afterwards.
    try:
        import importlib.metadata as md
        version = md.version("policyengine-us")
    except Exception:  # pragma: no cover - metadata absent in odd installs
        version = "unknown"
    meta = {"n_cases": len(cases), "seed": args.seed,
            "incomes": incomes, "household_space": space,
            "fields": list(FIELDS), "sweepable": SWEEPABLE,
            "engine": f"policyengine-us=={version}",
            "engine_calls": oracle.calls,
            "build_seconds": round(time.time() - started, 1)}
    Path(args.out).with_suffix(".meta.json").write_text(
        json.dumps(meta, indent=1, sort_keys=True))

    print(f"\n  {len(cases)} cases, {oracle.calls} engine calls, "
          f"{time.time()-started:.0f}s")
    print(f"  oracle: policyengine-us=={version}")
    print(f"  cache hits saved {len(cases) * 2 ** len(FIELDS) - oracle.calls:,} "
          "evaluations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
