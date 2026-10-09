#!/usr/bin/env python3
"""
Record the four numbers that carried rounds M and N but lived only in prose.

Why this script exists
----------------------
The argument that `award_aware_scorer` and `signed_scorer` are no-ops in
deployment rests on four figures: that the selector asks for `dependents`
first in every case that asks anything (447 of 447), that at τ = 0.3 the
three scorers commit immediately on 225 / 129 / 0 cases, and that 2.78% of
reachable state pairs reorder.

All four were measured ad hoc and typed into `docs/preregistration-5.md` and
`src/abstain/scorer.py`. None was in `evidence/`, so none was coupled to a
test — which is the defect the write-up-coupling tests exist to catch, and
they could not catch these because nothing to check against existed. The
figure-allocation numbers went the same way one round earlier and were fixed
the same way: by recording the run, not by relaxing the claim.

Fast on purpose. It touches no validation loop, so it can be re-run whenever
the scorers or the selector change, which is when these numbers would go
stale.
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.evaluate import OPENING  # noqa: E402
from abstain.rule import _default_choice, run_case  # noqa: E402
from abstain.scorer import (award_aware_scorer,  # noqa: E402
                            handcrafted_scorer, signed_scorer)
from abstain.validate import states_of  # noqa: E402

TAU = 0.3
FLIP_PAIRS = 100_000
FLIP_SEED = 89

SCORERS = (("handcrafted", handcrafted_scorer),
           ("award-aware", award_aware_scorer),
           ("signed", signed_scorer))

FIELDS = ("employment_income", "dependents", "age", "state_name")


def first_question(cases: list[dict], scorer, tau: float) -> dict:
    """
    Which field the greedy selector asks for first.

    Reported two ways, because the write-up quotes the second and the first
    is the stronger statement:

    `all_cases` asks the selector directly for every case, so the count does
    not depend on a threshold at all. `asking_cases` restricts to the cases
    that actually ask something at τ — which is where the published "447 of
    447" comes from, since 672 − 225 immediate commits leaves 447. Both are
    recorded so neither has to be re-derived by a reader.
    """
    everywhere: dict[str, int] = {f: 0 for f in FIELDS}
    asking: dict[str, int] = {f: 0 for f in FIELDS}
    n_asking = 0
    for c in cases:
        remaining = [f for f in FIELDS if f not in OPENING]
        pick = _default_choice(c, OPENING, remaining, scorer)
        everywhere[pick] += 1
        if run_case(c, scorer, tau).asked:
            asking[pick] += 1
            n_asking += 1
    return {"all_cases": everywhere, "asking_cases": asking,
            "n_asking": n_asking}


def immediate_commits(cases: list[dict], scorer, tau: float) -> int:
    """How many cases the rule answers without asking anything, at τ."""
    return sum(1 for c in cases
               if run_case(c, scorer, tau).asked == [])


def flip_rate(cases: list[dict], a, b) -> dict:
    """
    How often two scorers order a pair of reachable states differently.

    Uniform over *pairs*, fixed seed. The retracted version of this number
    took `states_of(cases)[:700]` — a prefix in case order, so every state
    in it fell in one band, where the term does not apply at all. The bug
    was the prefix, not the missing filter, so both are fixed here and the
    sampling is the part worth stating.
    """
    pool = [(c, k) for c, k, _ in states_of(cases) if OPENING <= k]
    rng = random.Random(FLIP_SEED)
    flips = ties = n = 0
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
    return {"reachable_states": len(pool), "pairs_sampled": FLIP_PAIRS,
            "comparable": n, "ties": ties, "flips": flips,
            "flip_rate": flips / n if n else 0.0, "seed": FLIP_SEED}


def main() -> int:
    t0 = time.time()
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, tau = {TAU}")

    print("\n  which field does the selector ask for first?")
    firsts = {}
    for label, scorer in SCORERS:
        d = first_question(cases, scorer, TAU)
        firsts[label] = d
        every, ask = d["all_cases"], d["asking_cases"]
        top = max(every, key=every.get)
        print(f"  {label:>13}  {top} in {every[top]} of {len(cases)} cases, "
              f"and in {ask[top]} of the {d['n_asking']} that ask anything")

    print(f"\n  cases committed to with no question asked, at tau = {TAU}")
    commits = {}
    for label, scorer in SCORERS:
        n = immediate_commits(cases, scorer, TAU)
        commits[label] = n
        print(f"  {label:>13}  {n:>4} of {len(cases)}")

    print("\n  order flips against the handcrafted scorer")
    flips = {}
    for label, scorer in SCORERS:
        if label == "handcrafted":
            continue
        f = flip_rate(cases, scorer, handcrafted_scorer)
        flips[label] = f
        print(f"  {label:>13}  {f['flip_rate']:.2%} of {f['comparable']:,} "
              f"comparable pairs ({f['ties']:,} tied)")

    payload = {"set": "fine_dev", "cases": len(cases), "tau": TAU,
               "first_question": firsts,
               "immediate_commits": commits,
               "order_flips": flips,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "opening_state.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
