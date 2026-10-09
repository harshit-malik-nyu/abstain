#!/usr/bin/env python3
"""
Round O — the arm round J skipped, and the tolerance it never tested.

`docs/preregistration-5.md`, addendum eight, committed before this file
existed. O1–O5 are fixed there and nothing below is adjusted after a result.

Why this round exists
---------------------
J1 refuted this repository's central claim: removing the distance feature cut
the subgroup concentration from 4.13 to 1.72 and put every band inside the
budget. That result has been reported prominently for two rounds and never
attacked, and it has a visible weakness — the no-distance scorer's worst band
is 12.48% at α = 0.20 and 11.65% at α = 0.15. It barely moves while the budget
falls by a quarter. A rule tracking its budget does not behave like that; a
near-constant failure rate with the budget sliding past it does.

So α = 0.10 is the test, and round J stopped at 0.15.

Round J also never ran group conditioning on this scorer — `schemes` in
`evidence/fitted_conditional.json` carries `handcrafted` and `fitted` only. So
every comparison published between "removing the feature" and "conditioning"
has been a *pooled* no-distance rule against a *group-conditioned* handcrafted
one. Both arms are run here.

Protocol, matched to round J so the arms are paired against published figures:
`fine_dev`, 200 trials, seed 53, 30% calibration share, the scorer refit every
trial on a fold disjoint from calibration and deployment.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import BANDS, Breakdown, collector  # noqa: E402
from abstain.group import validate_groups  # noqa: E402
from abstain.scorer import FittedScorer, auc, handcrafted_scorer  # noqa: E402
from abstain.validate import states_of, validate  # noqa: E402

# α = 0.10 is the point of the round. 0.20 and 0.15 are re-run rather than
# read from round J's file, so all three sit in one payload under one seed and
# O2's comparison is within-run rather than across two files.
ALPHAS = (0.20, 0.15, 0.10)
TRIALS = 200
SEED = 53
CALIBRATION_SHARE = 0.30

NO_DISTANCE = ("log_distance", "income_known")


def refit_no_distance(fit_cases: list[dict]):
    """The round-J model with distance from the eligibility boundary gone."""
    samples = list(states_of(fit_cases))
    return FittedScorer().fit(samples, epochs=250, lr=0.5,
                              exclude=NO_DISTANCE)


def ordering(cases: list[dict], refit_fn) -> float:
    third = len(cases) // 3
    active, held = refit_fn(cases[:third]), cases[third:]
    return auc([(active(c, k), d) for c, k, d in states_of(held)])


def measure(cases: list[dict], label: str, refit_fn) -> list[dict]:
    a = ordering(cases, refit_fn)
    print(f"\n  {label}: AUC {a:.4f} (fit and scored on disjoint folds)")
    out = []
    for alpha in ALPHAS:
        bd = Breakdown(alpha=alpha)
        v = validate(cases, None, alpha=alpha, trials=TRIALS, seed=SEED,
                     calibration_share=CALIBRATION_SHARE, refit=refit_fn,
                     on_trial=collector(bd))
        d = bd.as_dict() | {"scorer": label, "auc": a,
                            "mean_coverage": v.mean_coverage,
                            "mean_questions": v.mean_questions,
                            "violation_rate_when_feasible":
                                v.violation_rate_when_feasible,
                            "feasible_trials": sum(t.feasible
                                                   for t in v.results)}
        out.append(d)

        worst = d["worst_band"]
        rate = next(b["unsafe_rate"] for b in d["bands"]
                    if b["band"] == worst)
        print(f"\n  {label}, alpha = {alpha:.2f}   pooled "
              f"{bd.pooled_unsafe_rate:.2%}   coverage {v.mean_coverage:.2%}"
              f"   worst band {worst} at {rate:.2%}"
              f"   hides a subgroup: {bd.hides_a_subgroup}")
        print(f"  {'band':>16} {'unsafe':>8} {'cov':>8} {'conc':>7}")
        for row in d["bands"]:
            print(f"  {row['band']:>16} {row['unsafe_rate']:>7.2%} "
                  f"{row['coverage']:>7.2%} "
                  f"{d['concentration'][row['band']]:>7.2f}")
    return out


def conditioning(cases: list[dict]) -> list[dict]:
    """O3 and O4: does conditioning still add anything with the feature gone?"""
    print("\n  O3/O4 — group conditioning on the no-distance scorer")
    print(f"  {'scorer':>19} {'alpha':>6} {'scheme':>10} {'feas':>6} "
          f"{'grp-viol':>9} {'worst':>8} {'cov':>7}")
    out = []
    arms = (("handcrafted", handcrafted_scorer, None),
            ("fitted-no-distance", None, refit_no_distance))
    for label, scorer, refit_fn in arms:
        for alpha in ALPHAS:
            for scheme in ("pooled", "by-band"):
                v = validate_groups(cases, scorer, scheme=scheme,
                                    alpha=alpha, trials=TRIALS, seed=SEED,
                                    calibration_share=CALIBRATION_SHARE,
                                    refit=refit_fn)
                d = v.as_dict() | {"scorer": label}
                out.append(d)
                gv = d["group_violation_rate_when_feasible"]
                print(f"  {label:>19} {alpha:>6.2f} {scheme:>10} "
                      f"{d['feasible_trials']:>6} "
                      f"{'n/a' if gv is None else f'{gv:.1%}':>9} "
                      f"{d['mean_worst_group_rate']:>7.2%} "
                      f"{d['mean_coverage']:>6.2%}")
        print()
    return out


def worst_rate(row: dict) -> float:
    return next(b["unsafe_rate"] for b in row["bands"]
                if b["band"] == row["worst_band"])


def score(blind: list[dict], schemes: list[dict]) -> dict:
    """O1-O5 against addendum eight, which fixes every threshold used here."""
    at = {r["alpha"]: r for r in blind}
    ten, twenty = at[0.10], at[0.20]

    nd_byband = {s["alpha"]: s for s in schemes
                 if s["scorer"] == "fitted-no-distance"
                 and s["scheme"] == "by-band"}
    b10 = nd_byband[0.10]

    out = {
        "O1": {"claim": "no-distance worst band above 10% at alpha 0.10, "
                        "hides_a_subgroup True",
               "worst_rate": worst_rate(ten),
               "hides": ten["hides_a_subgroup"],
               "held": worst_rate(ten) > 0.10 and ten["hides_a_subgroup"]},
        "O2": {"claim": "its rate at 0.10 within 2 points of its rate at 0.20",
               "gap": abs(worst_rate(ten) - worst_rate(twenty)),
               "held": abs(worst_rate(ten) - worst_rate(twenty)) <= 0.02},
        "O3": {"claim": "conditioning brings the worst band under alpha "
                        "at 0.10 in feasible trials",
               "worst": b10["mean_worst_group_rate"],
               "feasible": b10["feasible_trials"],
               "held": (b10["feasible_trials"] > 0
                        and b10["mean_worst_group_rate"] < 0.10)},
        "O4": {"claim": "fewer than 190 of 200 feasible at alpha 0.10",
               "feasible": b10["feasible_trials"],
               "at_020": nd_byband[0.20]["feasible_trials"],
               "held": b10["feasible_trials"] < 190},
        "O5": {"claim": "well-below stays the worst band at every tolerance",
               "bands": {r["alpha"]: r["worst_band"] for r in blind},
               "held": all(r["worst_band"] == "well-below" for r in blind)},
    }
    print("\n  O1-O5, scored against addendum eight")
    for k, v in out.items():
        print(f"  {k}  {'held' if v['held'] else 'MISSED':>6}   {v['claim']}")
    return out


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}")
    print(f"  alphas {ALPHAS}; the scorer is refit per trial on a disjoint "
          f"third")

    t0 = time.time()
    blind = measure(cases, "fitted-no-distance", refit_no_distance)
    schemes = conditioning(cases)
    scored = score(blind, schemes)

    print("\n  the no-distance scorer against its own budget")
    print(f"  {'alpha':>6} {'worst band':>16} {'its rate':>9} {'budget':>7} "
          f"{'inside':>7} {'pooled':>8} {'cov':>7}")
    for r in blind:
        rate = worst_rate(r)
        print(f"  {r['alpha']:>6.2f} {str(r['worst_band']):>16} "
              f"{rate:>8.2%} {r['alpha']:>6.0%} "
              f"{'yes' if rate <= r['alpha'] else 'NO':>7} "
              f"{r['pooled_unsafe_rate']:>7.2%} {r['mean_coverage']:>6.2%}")

    payload = {"set": "fine_dev", "trials": TRIALS, "seed": SEED,
               "alphas": list(ALPHAS),
               "calibration_share": CALIBRATION_SHARE, "bands": list(BANDS),
               "no_distance_excludes": list(NO_DISTANCE),
               "fitted-no-distance": blind,
               "schemes": schemes,
               "predictions": scored,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "no_distance_groups.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
