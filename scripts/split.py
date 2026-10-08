#!/usr/bin/env python3
"""
Split the benchmark before any method exists.

Why this runs first
-------------------
The failure mode of a method paper is tuning against the evaluation until it
wins, then reporting the win. It is rarely deliberate. It happens one
reasonable decision at a time: a threshold adjusted after seeing a result, a
hyperparameter chosen because the other looked worse, a case excluded because
it seemed unrepresentative.

The only reliable defence is not having access. So the split happens now, in
the first commit of this repository, before a line of method code is written.
The git history is the evidence — anyone can check that this commit precedes
everything else.

What the halves are for
-----------------------
    dev        everything. Build on it, tune on it, look as often as you like.
    holdout    opened once, when the method is final, and reported whatever
               it says.

A result on dev is a demonstration. A result on holdout is a result. The
distinction only holds if the second set is genuinely untouched, which is why
this also writes a SHA-256 of each half: a later run producing different
contents is visible rather than silent.

Stratification
--------------
Cases are split stratified by how many of their knowledge states are
underdetermined, so the two halves contain comparable mixes of easy and hard
problems. With sixteen cases an unstratified draw could easily load one half
with the decidable ones, and then the halves would be measuring different
things rather than the same thing twice.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260408


def hardness(case: dict) -> str:
    """
    Stratum label: where does this household sit relative to the threshold?

    The first attempt stratified on the share of knowledge states that are
    underdetermined, and a test caught that it stratified on nothing: fifteen
    of sixteen cases fell in one bucket, because almost every state is open
    when three of four fields are missing. A stratum variable with no variance
    is not stratification.

    Income relative to the eligibility boundary is what actually varies, and
    it is what drives how many questions a case needs: far below the
    threshold and the answer is clear, far above and it is clear the other
    way, near it and nothing is decidable without more information.
    """
    income = case["household"]["employment_income"]
    if income <= 6_000:
        return "well-below"
    if income <= 24_000:
        return "near-threshold"
    if income <= 36_000:
        return "above"
    return "well-above"


def main() -> int:
    # Options added long after this file was written, to split a second,
    # larger benchmark without a third copy of the stratification logic. The
    # defaults reproduce the original call exactly, and that is verified
    # rather than asserted: `tests/test_split.py` re-runs the default and
    # checks the digests against the ones committed here in the first commit.
    # If this edit had changed the original split, that test fails.
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="cases.json")
    ap.add_argument("--prefix", default="",
                    help="written as <prefix>dev.json / <prefix>holdout.json")
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    source = ROOT / "evidence" / args.source
    if not source.exists():
        print(f"  evidence/{args.source} not built yet — "
              "run scripts/build_cases.py")
        return 1
    table = json.loads(source.read_text())
    rng = random.Random(args.seed)

    by_stratum: dict[str, list] = {}
    for case in table:
        by_stratum.setdefault(hardness(case), []).append(case)

    dev, holdout = [], []
    for _, cases in sorted(by_stratum.items()):
        shuffled = cases[:]
        rng.shuffle(shuffled)
        half = len(shuffled) // 2
        dev.extend(shuffled[:half])
        holdout.extend(shuffled[half:])

    for name, rows in ((f"{args.prefix}dev", dev),
                       (f"{args.prefix}holdout", holdout)):
        payload = json.dumps(rows, separators=(",", ":"), sort_keys=True)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        (ROOT / "evidence" / f"{name}.json").write_text(payload)
        (ROOT / "evidence" / f"{name}.sha256").write_text(digest + "\n")

        strata: dict[str, int] = {}
        for c in rows:
            strata[hardness(c)] = strata.get(hardness(c), 0) + 1
        print(f"  {name:8s} {len(rows):>3} cases  {strata}")
        print(f"           sha256 {digest}")

    print(f"\n  seed {args.seed}, stratified by income band")
    print("  holdout is opened once, when the method is final")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
