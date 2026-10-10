#!/usr/bin/env python3
"""
Re-run the two experiments behind claim 2, which had no script and no test.

What was wrong
--------------
`docs/theory.md` §2 — "the calibration unit must match the deployment unit",
one of the four numbered claims — rested on two figures:

> Measured consequence: **11%** of trials violated a 5% target, with the
> scorer refit on a disjoint fold so leakage is excluded. Calibrating on
> commitments instead takes it to **0%**.

Both came from `evidence/leakage.json` and `evidence/unit_comparison.json`,
added at **commit 6**. The fix for this repository's third bug —
`violation_rate_when_feasible`, so that a declined calibration is not scored
as a pass — landed at **commit 13**. So those files report
`violation_rate` pooled over trials the procedure *declined*, which is
exactly the defect the README documents, in evidence that predates its fix.

The consequences, read off the old files directly:

- The 11% is 11 violations in 100 trials of which **76 were infeasible.**
  Conditioned on feasibility it is roughly four times that.
- The 0% is zero violations in **100% infeasible** trials. There was no
  guarantee to test, and the honest statement is not that it held.

Neither file was written by any script in the repository, so neither could be
regenerated, and no test read them, so the write-up-coupling discipline never
reached the two figures. This script closes all three gaps: it regenerates
both files, reports the feasibility-conditioned metric, and
`tests/test_writeup_matches_evidence.py` reads what it writes.

What is deliberately *not* changed
----------------------------------
The arms, tolerances, trial counts and dataset are the ones the old files
record, so the new numbers are comparable to the old. Only the metric
changes, and both are reported side by side. The old files are kept under
`*-precorrection.json` rather than overwritten — a pre-fix run beside its fix
is this repository's standing practice.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.scorer import FittedScorer, handcrafted_scorer  # noqa: E402
from abstain.validate import states_of, validate  # noqa: E402

# Read off the files being replaced, not chosen now.
UNIT_ALPHAS = (0.10, 0.05)
UNIT_TRIALS = 80
LEAK_ALPHAS = (0.10, 0.05, 0.02)
LEAK_TRIALS = 100
DELTA = 0.05
SEED = 0


def refit(fit_cases: list[dict]):
    return FittedScorer().fit(list(states_of(fit_cases)), epochs=250, lr=0.5)


def leaked_scorer(cases: list[dict]):
    """
    A scorer fit on the whole pool, which is the arm that demonstrates
    leakage. It is built once and handed to every trial, so each trial's
    deployment cases were in its training set.
    """
    return FittedScorer().fit(list(states_of(cases)), epochs=250, lr=0.5)


def population_table(cases: list[dict], tau: float = 0.82) -> dict:
    """
    The three populations claim 2 is about, computed rather than remembered.

    This table — 1,264 calibration states against the 55 the rule commits
    at — is the mechanism behind claim 2 and the part of it that survived
    the retraction. Two of its three rows reproduce exactly from the
    benchmark. The middle one did not: the write-up carried **314 states,
    57.0% undetermined** and no script or evidence file recorded how that
    was counted, so it could not be checked or reproduced. Same defect as
    the 11%, in the same table.

    The definition used here, stated so the number is checkable: a state the
    rule **visits** is the opening state plus one state per question asked,
    per case, counted once each. A state it **commits at** is the final
    state of a case that committed.
    """
    from abstain.evaluate import OPENING
    from abstain.rule import run_case
    from abstain.scorer import handcrafted_scorer

    allst = list(states_of(cases))
    out = {
        "threshold": tau,
        "definition": ("visited = opening state plus one per question asked, "
                       "per case; committed = final state of a case that "
                       "committed"),
        "calibration_population": {
            "states": len(allst),
            "undetermined_share": sum(1 for _, _, d in allst if not d)
            / len(allst) if allst else 0.0,
        },
    }

    visited = committed = v_und = c_und = 0
    for c in cases:
        t = run_case(c, handcrafted_scorer, tau)
        known = set(OPENING)
        seq = [frozenset(known)]
        for f in t.asked:
            known.add(f)
            seq.append(frozenset(known))
        for k in seq:
            st = c["states"]["|".join(sorted(k))]
            visited += 1
            v_und += st["label"] != "determinable"
        if t.committed:
            st = c["states"]["|".join(sorted(seq[-1]))]
            committed += 1
            c_und += st["label"] != "determinable"

    out["states_the_rule_visits"] = {
        "states": visited,
        "undetermined_share": v_und / visited if visited else 0.0,
    }
    out["states_it_commits_at"] = {
        "states": committed,
        "undetermined_share": c_und / committed if committed else 0.0,
    }
    return out


def band_undetermined(cases: list[dict]) -> dict:
    """
    Each band's share of reachable states that are undecidable.

    `docs/preregistration-5.md` carries this table and two of its four
    cells are slightly off — 75.3% and 31.9% against a measured 75.5% and
    32.6%. A pre-registration is not edited after the fact, so the figures
    are recorded here and the document gets a correction note instead.
    """
    from abstain.conditional import undetermined_share
    return undetermined_share(cases)


def leakage_sweep(cases: list[dict]) -> list[dict]:
    """
    The three-scorer comparison behind the `refit` parameter's rationale.

    `validate.refit` and `group.validate_groups` both justify themselves in
    their docstrings with **"a logistic scorer fit on the whole pool
    violated a 5% target in 35.8% of trials, while a handcrafted scorer with
    no training step violated none."** That figure comes from
    `evidence/validation_dev.json`, which had no producing script and no
    reading test — the same gap that let claim 2's figures stay wrong.

    This one checks out: the 35.8% row has `infeasible_rate` 0.000, so the
    unconditional rate it reports equals the feasibility-conditioned one and
    the figure is sound. But it was sound by luck rather than by check, and
    the manifest had the file listed as referenced by nothing because the
    reference is in a module docstring rather than the write-up.

    Arms, tolerances and trial count read off the file being replaced.
    """
    from abstain.robustness import constant

    print("\n  the `refit` rationale — three scorers, leaked where fitted")
    print(f"  {'scorer':>12} {'alpha':>6} {'feas':>5} {'viol|feas':>10} "
          f"{'cov':>7}")
    leaked = leaked_scorer(cases)
    arms = (("handcrafted", handcrafted_scorer),
            ("fitted", leaked),
            ("constant", constant(0.5)))
    out = []
    for label, scorer in arms:
        for alpha in (0.20, 0.10, 0.05, 0.02):
            v = validate(cases, scorer, alpha=alpha, delta=DELTA,
                         trials=120, seed=SEED)
            r = row(v, alpha=alpha, trials=120, scorer=label)
            out.append(r)
            vf = r["violation_rate_when_feasible"]
            print(f"  {label:>12} {alpha:>6.2f} {r['feasible_trials']:>5} "
                  f"{'n/a' if vf is None else f'{vf:>9.1%}'} "
                  f"{r['mean_coverage']:>6.1%}")
    return out


def unit_by_leakage(cases: list[dict]) -> list[dict]:
    """
    The cross that shows what the 35.8% actually measures.

    `validate.refit` and `group.validate_groups` justify themselves with
    "a logistic scorer fit on the whole pool violated a 5% target in 35.8%
    of trials, while a handcrafted scorer with no training step violated
    none." The figure reproduces — 36.7% at a fresh fit — but only under
    **state-unit** calibration, which is the unit claim 2 of
    `docs/theory.md` argues is the wrong one.

    Under the trajectory unit the method actually uses, alpha = 0.05 is
    infeasible for every arm on dev, so the leakage effect cannot be
    measured there at all. Both facts need to be visible together, so this
    runs the full cross.
    """
    from abstain.robustness import constant

    leaked = leaked_scorer(cases)
    print("\n  what the 35.8% measures — unit x leakage, alpha = 0.05")
    print(f"  {'scorer':>14} {'unit':>11} {'feas':>5} {'viol|feas':>10} "
          f"{'cov':>7}")
    out = []
    arms = (("handcrafted", handcrafted_scorer, None),
            ("fitted-leaked", leaked, None),
            ("fitted-refit", None, refit),
            ("constant", constant(0.5), None))
    for label, scorer, fn in arms:
        for unit in ("state", "trajectory"):
            v = validate(cases, scorer, alpha=0.05, delta=DELTA, trials=120,
                         seed=SEED, unit=unit, refit=fn)
            r = row(v, alpha=0.05, trials=120, scorer=label, unit=unit)
            out.append(r)
            vf = r["violation_rate_when_feasible"]
            print(f"  {label:>14} {unit:>11} {r['feasible_trials']:>5} "
                  f"{'n/a' if vf is None else f'{vf:>9.1%}'} "
                  f"{r['mean_coverage']:>6.1%}")
    return out


def row(v, *, alpha: float, trials: int, **extra) -> dict:
    d = v.as_dict()
    feasible = sum(t.feasible for t in v.results)
    out = {
        "alpha": alpha, "delta": DELTA, "trials": trials,
        "feasible_trials": feasible,
        "infeasible_rate": 1.0 - feasible / len(v.results) if v.results
        else 1.0,
        # The metric the old files did not have. None, never 0.0, when no
        # trial was certified -- "never tested" is not "held".
        "violation_rate_when_feasible": v.violation_rate_when_feasible,
        # Kept so the correction is legible beside what it corrects.
        "violation_rate_pooled_over_declined": d["violation_rate"],
        "mean_coverage": v.mean_coverage,
        "mean_questions": v.mean_questions,
        "holds": v.holds,
    }
    return out | extra


def unit_comparison(cases: list[dict]) -> list[dict]:
    print("\n  claim 2 — calibration unit, with the scorer refit per trial")
    print(f"  {'unit':>12} {'alpha':>6} {'feas':>5} {'viol|feas':>10} "
          f"{'viol pooled':>12} {'cov':>7}")
    out = []
    for unit in ("state", "trajectory"):
        for alpha in UNIT_ALPHAS:
            v = validate(cases, None, alpha=alpha, delta=DELTA,
                         trials=UNIT_TRIALS, seed=SEED, unit=unit,
                         refit=refit)
            r = row(v, alpha=alpha, trials=UNIT_TRIALS, unit=unit,
                    scorer="fitted, refit per trial")
            out.append(r)
            vf = r["violation_rate_when_feasible"]
            print(f"  {unit:>12} {alpha:>6.2f} {r['feasible_trials']:>5} "
                  f"{'n/a' if vf is None else f'{vf:>9.1%}'} "
                  f"{r['violation_rate_pooled_over_declined']:>11.1%} "
                  f"{r['mean_coverage']:>6.1%}")
    return out


def leakage(cases: list[dict]) -> list[dict]:
    print("\n  leakage — a scorer fit on the pool it is scored on")
    print(f"  {'arrangement':>34} {'alpha':>6} {'feas':>5} "
          f"{'viol|feas':>10} {'viol pooled':>12} {'cov':>7}")
    leaked = leaked_scorer(cases)
    out = []
    arms = (("fitted on the whole pool (leaked)", leaked, None),
            ("refit on a disjoint fold", None, refit))
    for label, scorer, fn in arms:
        for alpha in LEAK_ALPHAS:
            v = validate(cases, scorer, alpha=alpha, delta=DELTA,
                         trials=LEAK_TRIALS, seed=SEED, refit=fn)
            r = row(v, alpha=alpha, trials=LEAK_TRIALS, arrangement=label)
            out.append(r)
            vf = r["violation_rate_when_feasible"]
            print(f"  {label:>34} {alpha:>6.2f} {r['feasible_trials']:>5} "
                  f"{'n/a' if vf is None else f'{vf:>9.1%}'} "
                  f"{r['violation_rate_pooled_over_declined']:>11.1%} "
                  f"{r['mean_coverage']:>6.1%}")
    return out


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "dev.json").read_text())
    print(f"  dev: {len(cases)} cases  (the half these experiments used)")
    print("  arms, tolerances and trial counts read off the files being "
          "replaced")

    t0 = time.time()
    for name in ("unit_comparison", "leakage"):
        src = ROOT / "evidence" / f"{name}.json"
        dst = ROOT / "evidence" / f"{name}-precorrection.json"
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"  kept the pre-correction run as {dst.name}")

    pop = population_table(cases)
    print("\n  claim 2's mechanism — the three populations, at tau = 0.82")
    for key in ("calibration_population", "states_the_rule_visits",
                "states_it_commits_at"):
        d = pop[key]
        print(f"  {key:>26}  {d['states']:>5,} states  "
              f"{d['undetermined_share']:>6.1%} undetermined")

    fine = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    bands = {"dev": band_undetermined(cases),
             "fine_dev": band_undetermined(fine)}
    print("\n  share of reachable states undetermined, per band")
    for name, d in bands.items():
        print(f"  {name:>9}  " +
              "  ".join(f"{b}={v:.1%}" for b, v in d.items()))

    units = unit_comparison(cases)
    leaks = leakage(cases)
    rationale = leakage_sweep(cases)
    cross = unit_by_leakage(cases)

    for name, payload in (("unit_comparison", units), ("leakage", leaks),
                          ("refit_rationale",
                           {"sweep": rationale, "unit_by_leakage": cross}),
                          ("unit_populations",
                           {"threshold": pop["threshold"],
                            "definition": pop["definition"],
                            "populations": {k: pop[k] for k in
                                            ("calibration_population",
                                             "states_the_rule_visits",
                                             "states_it_commits_at")},
                            "band_undetermined_share": bands})):
        dest = ROOT / "evidence" / f"{name}.json"
        dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
        print(f"\n  wrote {dest.relative_to(ROOT)}")

    print(f"\n  {round(time.time() - t0, 1)}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
