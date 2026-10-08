#!/usr/bin/env python3
"""
Is the subgroup failure a property of the threshold, or of the agent's
question policy?

The confound
------------
The rule does two things: it decides **when** to stop asking, and it decides
**what** to ask next. The subgroup finding is attributed entirely to the first
— a single global threshold cuts bands whose score distributions are shifted
at different quantiles. But the second could produce something that looks the
same. `_default_choice` is a greedy one-step lookahead, and a question policy
that happens to serve one band badly would concentrate the error budget there
without the threshold having anything to do with it.

Nothing in the write-up ruled that out, so this does.

The test
--------
Hold everything else fixed and swap the question policy for two alternatives
that cannot be serving any band strategically:

    greedy        the default. Asks whichever field most raises the score.
    fixed order   always dependents, then state, then age, then income.
                  Blind to the case.
    random order  a different field each time, seeded per state so the
                  scorer stays a function.

If the concentration is a threshold property it survives all three. If it is
a question-policy artefact it should move a lot or change which band fails.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import abstain.rule as rule_module  # noqa: E402
from abstain.conditional import Breakdown, collector  # noqa: E402
from abstain.scorer import handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

TRIALS = 200
SEED = 31
CALIBRATION_SHARE = 0.30
ALPHAS = (0.20, 0.15)

FIXED = ("dependents", "state_name", "age", "employment_income")


def fixed_order(case, known, remaining, scorer):
    for f in FIXED:
        if f in remaining:
            return f
    return remaining[0]


def random_order(case, known, remaining, scorer):
    # Seeded from the state, not drawn fresh: the rule evaluates a state more
    # than once and a policy that answers differently each time is not a
    # policy. Same reason `robustness.noisy` is deterministic, and the same
    # SHA-256 rather than hash(), which Python salts per process.
    key = f"{case.get('id', -1)}|{','.join(sorted(known))}"
    seed = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big")
    return random.Random(seed).choice(sorted(remaining))


POLICIES = (("greedy (default)", None),
            ("fixed order", fixed_order),
            ("random order", random_order))


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}")
    print("  Does the concentration survive a different question policy?\n")

    original = rule_module._default_choice
    out = []
    try:
        for alpha in ALPHAS:
            print(f"  alpha = {alpha:.2f}")
            print(f"  {'question policy':>18} {'pooled':>8} "
                  f"{'well-below':>11} {'conc':>7} {'worst band':>15} "
                  f"{'q/case':>8}")
            for name, policy in POLICIES:
                rule_module._default_choice = original if policy is None \
                    else policy

                bd = Breakdown(alpha=alpha)
                v = validate(cases, handcrafted_scorer, alpha=alpha,
                             trials=TRIALS, seed=SEED,
                             calibration_share=CALIBRATION_SHARE,
                             on_trial=collector(bd))
                d = bd.as_dict()
                wb = next(b for b in d["bands"] if b["band"] == "well-below")
                row = {"alpha": alpha, "policy": name,
                       "pooled_unsafe_rate": d["pooled_unsafe_rate"],
                       "well_below_unsafe_rate": wb["unsafe_rate"],
                       "concentration": d["concentration"]["well-below"],
                       "worst_band": d["worst_band"],
                       "hides_a_subgroup": d["hides_a_subgroup"],
                       "questions_per_case": v.mean_questions}
                out.append(row)
                print(f"  {name:>18} {d['pooled_unsafe_rate']:>7.1%} "
                      f"{wb['unsafe_rate']:>10.1%} "
                      f"{d['concentration']['well-below']:>7.2f} "
                      f"{str(d['worst_band']):>15} "
                      f"{v.mean_questions:>8.2f}")
            print()
    finally:
        rule_module._default_choice = original

    payload = {"set": "fine_dev", "trials": TRIALS, "seed": SEED,
               "calibration_share": CALIBRATION_SHARE, "rows": out}
    dest = ROOT / "evidence" / "confounds.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"  wrote {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
