#!/usr/bin/env python3
"""
Is the subgroup failure a property of the world, or of the fifty?

`docs/preregistration-5.md`, addendum five, committed before this file.

`build_cases.assess` calls a knowledge state undetermined when sweeping the
unknown fields either flips the eligibility verdict **or** moves the benefit
amount by more than `material = 50.0`. That fifty was chosen once, in the
first commit, and has been the definition of ground truth for every number in
this repository since.

Re-labelling needs no oracle calls. Every state records its `spread`, and
whether the verdict flipped is reconstructible from the complete enumeration,
because every household the sweep produces is itself in the benchmark. So the
labels can be recomputed at any materiality and the whole pipeline re-run
against them.

The reconstruction is checked against the committed labels at $50 before
anything else happens. If it cannot reproduce them, it is re-labelling
something other than this benchmark and no number below would mean anything.
"""

from __future__ import annotations

import copy
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import Breakdown, collector  # noqa: E402
from abstain.scorer import FIELDS, handcrafted_scorer  # noqa: E402
from abstain.validate import validate  # noqa: E402

SWEEPABLE = {
    "dependents": [0, 1, 2, 3],
    "employment_income": [0, 9_000, 18_000, 27_000, 36_000],
    "age": [22, 35, 50, 64],
    "state_name": ["NY", "TX", "CA", "MS"],
}

# Flip-only is represented as an unreachable materiality: no spread can
# exceed it, so only a verdict flip makes a state undetermined.
FLIP_ONLY = float("inf")
SETTINGS = [0.0, 25.0, 50.0, 100.0, 200.0, 500.0, FLIP_ONLY]

ALPHA = 0.20
TRIALS = 200
SEED = 71


def verdict_table(full_space: list[dict]) -> dict:
    return {tuple(c["household"][f] for f in FIELDS):
            c["states"]["|".join(sorted(FIELDS))]["truth"]
            for c in full_space}


def flips_and_spread(case: dict, known: tuple[str, ...],
                     verdict: dict) -> tuple[bool, float, str]:
    """Whether the verdict varies across the sweep, and by how much."""
    unknown = [f for f in FIELDS if f not in known]
    stored = case["states"]["|".join(sorted(known))]
    if not unknown:
        return False, 0.0, stored["truth"]

    hh = case["household"]
    seen = set()
    for combo in itertools.product(*[SWEEPABLE[f] for f in unknown]):
        trial = dict(hh)
        trial.update(dict(zip(unknown, combo)))
        seen.add(verdict[tuple(trial[f] for f in FIELDS)])
    return len(seen) > 1, float(stored.get("spread", 0.0)), next(iter(seen))


def relabel(cases: list[dict], verdict: dict, material: float) -> list[dict]:
    """The benchmark with determinability recomputed at `material`."""
    out = []
    for case in cases:
        fresh = copy.deepcopy(case)
        for r in range(len(FIELDS) + 1):
            for known in itertools.combinations(FIELDS, r):
                key = "|".join(sorted(known))
                flips, spread, settled = flips_and_spread(case, known,
                                                          verdict)
                if flips or spread > material:
                    fresh["states"][key] = {"label": "underdetermined",
                                            "truth": "cannot_determine",
                                            "spread": spread}
                else:
                    fresh["states"][key] = {"label": "determinable",
                                            "truth": settled,
                                            "spread": spread}
        out.append(fresh)
    return out


def check_reproduces_committed(cases: list[dict], verdict: dict) -> None:
    """At $50 the re-labelling must give back exactly what is committed."""
    rebuilt = relabel(cases, verdict, 50.0)
    for original, fresh in zip(cases, rebuilt):
        for key, state in original["states"].items():
            assert state["label"] == fresh["states"][key]["label"], (
                f"case {original['id']} state {key!r}: committed "
                f"{state['label']}, rebuilt {fresh['states'][key]['label']}")
            if state["label"] == "determinable":
                assert state["truth"] == fresh["states"][key]["truth"], (
                    f"case {original['id']} state {key!r}: verdict differs")
    print("  re-labelling at $50 reproduces the committed labels exactly\n")


def label(material: float) -> str:
    return "flip-only" if material == FLIP_ONLY else f"${material:.0f}"


def main() -> int:
    full = json.loads((ROOT / "evidence" / "cases_fine.json").read_text())
    dev = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    verdict = verdict_table(full)

    print(f"  fine_dev: {len(dev)} cases, {TRIALS} trials, seed {SEED}, "
          f"alpha {ALPHA}")
    check_reproduces_committed(dev, verdict)

    t0 = time.time()
    rows = []
    print(f"  {'materiality':>12} {'open states':>12} {'pooled':>8} "
          f"{'coverage':>9} {'worst band':>15} {'its rate':>9} {'conc':>7} "
          f"{'hides':>6}")
    for material in SETTINGS:
        cases = relabel(dev, verdict, material)

        total = sum(1 for c in cases for k, s in c["states"].items()
                    if "employment_income" in k.split("|"))
        open_ = sum(1 for c in cases for k, s in c["states"].items()
                    if "employment_income" in k.split("|")
                    and s["label"] == "underdetermined")

        bd = Breakdown(alpha=ALPHA)
        v = validate(cases, handcrafted_scorer, alpha=ALPHA, trials=TRIALS,
                     seed=SEED, calibration_share=0.30,
                     on_trial=collector(bd))
        d = bd.as_dict()
        worst = d["worst_band"]
        conc = d["concentration"].get(worst, 0.0) if worst else 0.0
        rate = next((b["unsafe_rate"] for b in d["bands"]
                     if b["band"] == worst), 0.0)

        rows.append(d | {"material": None if material == FLIP_ONLY
                         else material,
                         "flip_only": material == FLIP_ONLY,
                         "open_state_share": open_ / total if total else 0.0,
                         "mean_coverage": v.mean_coverage,
                         "worst_band_rate": rate,
                         "worst_concentration": conc})

        print(f"  {label(material):>12} {open_ / total:>11.1%} "
              f"{d['pooled_unsafe_rate']:>7.1%} {v.mean_coverage:>8.1%} "
              f"{str(worst):>15} {rate:>8.1%} {conc:>7.2f} "
              f"{str(d['hides_a_subgroup']):>6}")

    print("\n  Does the headline survive the parameter?")
    print("  " + "-" * 64)
    non_degenerate = [r for r in rows if r["mean_coverage"] > 0.05]
    worst_bands = {r["worst_band"] for r in non_degenerate}
    min_conc = min(r["worst_concentration"] for r in non_degenerate)
    print(f"  non-degenerate settings: {len(non_degenerate)} of {len(rows)}")
    print(f"  worst band across them:  {worst_bands}")
    print(f"  smallest concentration:  {min_conc:.2f}")

    payload = {"set": "fine_dev", "alpha": ALPHA, "trials": TRIALS,
               "seed": SEED, "rows": rows,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "materiality.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
