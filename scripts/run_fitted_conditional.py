#!/usr/bin/env python3
"""
Does a learned scorer concentrate the error budget too?

`docs/preregistration-5.md`, addendum two, committed before this file existed.

The subgroup finding so far rests on one hand-built scorer, and the mechanism
diagnosis traces its failure to one hand-written feature. If the concentration
is really a property of using a single threshold across groups whose score
distributions sit at different levels, then a scorer that learns its weights
from data must show it too. If it does not, the finding is about a toy scorer
and the write-up has to say so.

`FittedScorer` is refit every trial on a fold disjoint from both calibration
and deployment. That is not optional: a scorer fit on the calibration or
deployment data violated a 5% target in 35.8% of trials when this project
measured it, because the conformal argument needs the score fixed with respect
to both.
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
from abstain.scorer import FittedScorer, handcrafted_scorer  # noqa: E402
from abstain.validate import states_of, validate  # noqa: E402

ALPHAS = (0.20, 0.15)
TRIALS = 200
SEED = 53
CALIBRATION_SHARE = 0.30


NO_DISTANCE = ("log_distance", "income_known")


def refit_no_distance(fit_cases: list[dict]):
    """
    The same model with distance from the eligibility boundary removed.

    What remains is only which fields the agent knows. Such a scorer cannot
    represent the feature the mechanism diagnosis blames, so if the
    concentration came from that feature it must disappear here. It is a much
    weaker scorer and that is the point: the question is whether one threshold
    over ANY score spends its budget unevenly when the groups differ.
    """
    samples = [(c, k, determinable) for c, k, determinable
               in states_of(fit_cases)]
    return FittedScorer().fit(samples, epochs=250, lr=0.5,
                              exclude=NO_DISTANCE)


def refit(fit_cases: list[dict]):
    """
    Train on every knowledge state of the fitting fold.

    The label is the oracle's verdict for that state, which is legitimate
    supervision on past cases and unavailable at decision time.
    """
    samples = [(c, k, determinable) for c, k, determinable
               in states_of(fit_cases)]
    return FittedScorer().fit(samples, epochs=250, lr=0.5)


def ordering(cases: list[dict], scorer, refit_fn) -> float:
    """
    AUC of the arm's scorer, fit and evaluated on disjoint folds.

    Reported beside each breakdown so the concentration can be read against
    how good the ordering is. J4 is a claim about this number, and a claim
    about a number nobody computed is not a prediction.
    """
    from abstain.scorer import auc
    if refit_fn is None:
        active = scorer
        held = cases
    else:
        third = len(cases) // 3
        active, held = refit_fn(cases[:third]), cases[third:]
    return auc([(active(c, k), d) for c, k, d in states_of(held)])


def measure(cases: list[dict], scorer, label: str, refit_fn=None) -> list[dict]:
    auc_value = ordering(cases, scorer, refit_fn)
    print(f"\n  {label}: AUC {auc_value:.4f} (fit and scored on disjoint "
          f"folds)")
    out = []
    for alpha in ALPHAS:
        bd = Breakdown(alpha=alpha)
        v = validate(cases, scorer, alpha=alpha, trials=TRIALS, seed=SEED,
                     calibration_share=CALIBRATION_SHARE, refit=refit_fn,
                     on_trial=collector(bd))
        d = bd.as_dict() | {"scorer": label, "auc": auc_value,
                            "mean_coverage": v.mean_coverage,
                            "violation_rate_when_feasible":
                                v.violation_rate_when_feasible,
                            "feasible_trials": sum(t.feasible
                                                   for t in v.results)}
        out.append(d)

        worst = max(d["concentration"].values(), default=0.0)
        print(f"\n  {label}, alpha = {alpha:.2f}   pooled "
              f"{bd.pooled_unsafe_rate:.1%}   coverage {v.mean_coverage:.1%}"
              f"   worst band {bd.worst_band}   max concentration "
              f"{worst:.2f}   hides a subgroup: {bd.hides_a_subgroup}")
        print(f"  {'band':>16} {'deployed':>9} {'unsafe':>7} {'rate':>7} "
              f"{'cov':>7} {'conc':>7}")
        for row in d["bands"]:
            print(f"  {row['band']:>16} {row['deployed']:>9} "
                  f"{row['unsafe']:>7} {row['unsafe_rate']:>6.1%} "
                  f"{row['coverage']:>6.1%} "
                  f"{d['concentration'][row['band']]:>7.2f}")
    return out


def conditioning_helps(cases: list[dict]) -> list[dict]:
    """
    H4: does the fix work for the learned scorer as well?

    The first version of this function passed `handcrafted_scorer` to every
    arm, because `validate_groups` had no way to refit. It printed a table
    that looked like an answer to H4 and was a duplicate of round four's
    scheme comparison — the learned scorer never appeared in it. Nothing
    failed and nothing warned.

    Both scorers are run now, so H4 is answered and the control is visible
    beside it.
    """
    print("\n  H4 — does group conditioning fix the learned scorer too?")
    print(f"  {'scorer':>12} {'alpha':>6} {'scheme':>10} {'feas':>6} "
          f"{'grp-viol':>9} {'worst':>7} {'cov':>7}")
    out = []
    for label, scorer, refit_fn in (("handcrafted", handcrafted_scorer, None),
                                    ("fitted", None, refit)):
        for alpha in ALPHAS:
            for scheme in ("pooled", "by-band"):
                v = validate_groups(cases, scorer, scheme=scheme,
                                    alpha=alpha, trials=TRIALS, seed=SEED,
                                    calibration_share=CALIBRATION_SHARE,
                                    refit=refit_fn)
                d = v.as_dict() | {"scorer": label}
                out.append(d)
                gv = d["group_violation_rate_when_feasible"]
                print(f"  {label:>12} {alpha:>6.2f} {scheme:>10} "
                      f"{d['feasible_trials']:>6} "
                      f"{'n/a' if gv is None else f'{gv:.1%}':>9} "
                      f"{d['mean_worst_group_rate']:>6.1%} "
                      f"{d['mean_coverage']:>6.1%}")
        print()
    return out


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, {TRIALS} trials, seed {SEED}")
    print("  the fitted scorer is refit per trial on a disjoint third")

    t0 = time.time()
    hand = measure(cases, handcrafted_scorer, "handcrafted")
    fitted = measure(cases, None, "fitted", refit_fn=refit)
    blind = measure(cases, None, "fitted-no-distance",
                    refit_fn=refit_no_distance)
    schemes = conditioning_helps(cases)

    print("\n  H1/H2/J1/J2 — side by side at alpha = 0.20")
    print(f"  {'scorer':>19} {'pooled':>8} {'coverage':>9} "
          f"{'worst band':>15} {'its rate':>9} {'conc':>7}")
    for rows in (hand, fitted, blind):
        d = next(r for r in rows if r["alpha"] == 0.20)
        w = next(b for b in d["bands"] if b["band"] == d["worst_band"])
        print(f"  {d['scorer']:>19} {d['pooled_unsafe_rate']:>7.1%} "
              f"{d['mean_coverage']:>8.1%} {str(d['worst_band']):>15} "
              f"{w['unsafe_rate']:>8.1%} "
              f"{d['concentration'][d['worst_band']]:>7.2f}")

    payload = {"set": "fine_dev", "trials": TRIALS, "seed": SEED,
               "calibration_share": CALIBRATION_SHARE, "bands": list(BANDS),
               "handcrafted": hand, "fitted": fitted,
               "fitted-no-distance": blind,
               "no_distance_excludes": list(NO_DISTANCE),
               "schemes": schemes,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "fitted_conditional.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
