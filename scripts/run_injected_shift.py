#!/usr/bin/env python3
"""
Round S — cause the subgroup mechanism, instead of observing it.

`docs/preregistration-5.md`, addendum eleven, committed before this file and
before `robustness.band_shifted` existed. S1–S5, the sweep, the band, the
tolerance and the seed are fixed there and none is adjusted after a result.

What this round is for
----------------------
Every subgroup result in this repository is observational. One scorer was
measured, its budget was found to concentrate on the poorest income band, and
the concentration was traced to a feature reading distance-from-boundary as
safety. Rounds H, J and Q attacked that from outside and it survived in
narrowed form — but J1 also showed that the *reason* and the *mechanism* are
confounded: remove the one feature and the concentration falls to 1.72.

So the mechanism has never been isolated. `theory.md` §4 claims it is about
score **levels** differing between groups while the ranking inside each group
is fine. This injects exactly that property into the arm that does **not**
have it, and asks whether the stated consequence follows and the stated remedy
works.

Base: the no-distance fitted scorer, refit every trial on a fold disjoint from
calibration and deployment. Starting from the arm with concentration 1.72 and
no hidden subgroup is the point — anything this sweep produces was injected
rather than found.

A note on sampling, because this repository has been bitten three times
----------------------------------------------------------------------
While checking the injection, a prefix of `states_of(cases)` showed **zero**
scores lifted, which looked like the corruption not working. It was the same
defect as the retracted 106,365-pair claim: `states_of` iterates in case
order, so a prefix covers a few cases and can miss a band entirely or hit only
its zero-scoring states. Every check below runs over the whole population.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import Breakdown, collector, hardness  # noqa: E402
from abstain.group import trial_rate_interval, validate_groups  # noqa: E402
from abstain.robustness import band_shifted  # noqa: E402
from abstain.scorer import FittedScorer, auc  # noqa: E402
from abstain.validate import states_of, validate  # noqa: E402

BAND = "well-below"
KS = (0.0, 0.25, 0.5, 1.0, 2.0)
ALPHA = 0.20
TRIALS = 200
SEED = 61
CALIBRATION_SHARE = 0.30
NO_DISTANCE = ("log_distance", "income_known")


def refit_for(k: float):
    """
    A per-trial refit that fits the clean scorer, then injects the shift.

    The order matters and is the reason this is a function of `k` rather than
    a corruption of a fixed scorer: the model is trained on **unshifted**
    labels and features, and the shift is applied to its output afterwards.
    Training on shifted scores would let the model learn around the
    injection, which is a different experiment.
    """
    def refit(fit_cases: list[dict]):
        base = FittedScorer().fit(list(states_of(fit_cases)),
                                  epochs=250, lr=0.5, exclude=NO_DISTANCE)
        return base if k == 0.0 else band_shifted(base, BAND, k)
    return refit


def injection_properties(cases: list[dict]) -> list[dict]:
    """
    The three properties the pre-registration claims, measured on the whole
    population rather than asserted in a docstring.
    """
    third = len(cases) // 3
    base = FittedScorer().fit(list(states_of(cases[:third])),
                              epochs=250, lr=0.5, exclude=NO_DISTANCE)
    held = [(c, kn) for c, kn, _ in states_of(cases[third:])]
    inside = [(c, kn) for c, kn in held if hardness(c) == BAND]
    outside = [(c, kn) for c, kn in held if hardness(c) != BAND]
    if not inside:
        # Not reachable on `fine_dev`, where every band is populated and a
        # test asserts it. Guarded anyway because the first smoke test of
        # this function passed it a PREFIX of the case list, which contains
        # no `well-below` cases at all, and it died on a division rather
        # than saying what was wrong. Fourth time a prefix has misled this
        # repository; the message is cheaper than the next diagnosis.
        raise SystemExit(
            f"no {BAND} cases in the held-out fold -- if this was a prefix "
            f"of the case list, sample instead: states_of iterates in case "
            f"order and a prefix can miss a whole band")

    print(f"\n  the injection, measured on {len(held):,} held-out states "
          f"({len(inside):,} in {BAND})")
    print(f"  {'k':>6} {'identity':>9} {'outside':>9} {'monotone':>9} "
          f"{'mean lift':>10} {'max lift':>9} {'AUC':>8}")
    out = []
    for k in KS:
        f = base if k == 0.0 else band_shifted(base, BAND, k)
        pairs = [(base(c, kn), f(c, kn)) for c, kn in inside]
        untouched = all(base(c, kn) == f(c, kn) for c, kn in outside)
        srt = sorted(pairs)
        mono = all(y2 >= y1 - 1e-12
                   for (_, y1), (_, y2) in zip(srt, srt[1:]))
        identity = all(a == b for a, b in pairs)
        lifts = [b - a for a, b in pairs]
        a_val = auc([(f(c, kn), d) for c, kn, d in states_of(cases[third:])])
        row = {"k": k, "is_identity": identity,
               "outside_untouched": untouched, "monotone_inside": mono,
               "mean_lift": sum(lifts) / len(lifts), "max_lift": max(lifts),
               "auc": a_val}
        out.append(row)
        print(f"  {k:>6.2f} {str(identity):>9} {str(untouched):>9} "
              f"{str(mono):>9} {row['mean_lift']:>+10.4f} "
              f"{row['max_lift']:>+9.4f} {a_val:>8.4f}")
    return out


def sweep(cases: list[dict]) -> list[dict]:
    """
    The sweep, checkpointed per `k`.

    Five values of `k`, each refitting the scorer on every one of 200
    trials across three arms — about a quarter of an hour per `k`. Two
    long runs in this session were killed by the environment underneath
    them, so each `k` is appended to a JSONL as it finishes and a restart
    skips what is already there. Every arm is a pure function of its seed,
    so this changes nothing about what is computed.
    """
    print(f"\n  S1-S5 — alpha = {ALPHA}, {TRIALS} trials, band {BAND}")
    print(f"  {'k':>6} {'scheme':>8} {'feas':>5} {'grp-viol':>19} "
          f"{'worst band':>14} {'its rate':>9} {'conc':>6} {'cov':>7}")

    ckpt = ROOT / "evidence" / "injected_shift.partial.jsonl"
    done: dict[float, list[dict]] = {}
    if ckpt.exists():
        for line in ckpt.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done.setdefault(r["k"], []).append(r)
        print(f"  resuming: {len(done)} value(s) of k already in "
              f"{ckpt.name}")

    out = []
    for k in KS:
        if k in done and len(done[k]) == 2:
            for r in done[k]:
                out.append(r)
                w = r["worst_band"]
                gv = r["group_violation_rate_when_feasible"]
                lo, hi = r["group_violation_interval"]
                print(f"  {k:>6.2f} {r['scheme']:>8} "
                      f"{r['feasible_trials']:>5} "
                      f"{('n/a' if gv is None else f'{gv:.1%} [{lo:.1%},{hi:.1%}]'):>19} "
                      f"{str(w):>14} {r['concentration'].get(w, 0):>8.2f}x "
                      f"{r['mean_worst_group_rate']:>5.1%} "
                      f"{r['mean_coverage']:>6.1%}  (cached)")
            continue
        refit = refit_for(k)

        bd = Breakdown(alpha=ALPHA)
        validate(cases, None, alpha=ALPHA, trials=TRIALS, seed=SEED,
                 calibration_share=CALIBRATION_SHARE, refit=refit,
                 on_trial=collector(bd))
        brk = bd.as_dict()

        for scheme in ("pooled", "by-band"):
            v = validate_groups(cases, None, scheme=scheme, alpha=ALPHA,
                                trials=TRIALS, seed=SEED,
                                calibration_share=CALIBRATION_SHARE,
                                refit=refit)
            d = v.as_dict()
            gv = d["group_violation_rate_when_feasible"]
            n = d["feasible_trials"]
            lo, hi = trial_rate_interval(round((gv or 0.0) * n), n)
            row = {"k": k, "scheme": scheme,
                   "feasible_trials": n,
                   "group_violation_rate_when_feasible": gv,
                   "group_violation_interval": [lo, hi],
                   "mean_worst_group_rate": d["mean_worst_group_rate"],
                   "mean_coverage": d["mean_coverage"],
                   "worst_band": brk["worst_band"],
                   "concentration": brk["concentration"],
                   "hides_a_subgroup": brk["hides_a_subgroup"],
                   "band_rates": {b["band"]: b["unsafe_rate"]
                                  for b in brk["bands"]}}
            out.append(row)
            with ckpt.open("a") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            w = brk["worst_band"]
            print(f"  {k:>6.2f} {scheme:>8} {n:>5} "
                  f"{('n/a' if gv is None else f'{gv:.1%} [{lo:.1%},{hi:.1%}]'):>19} "
                  f"{str(w):>14} {brk['concentration'].get(w, 0):>8.2f}x "
                  f"{row['mean_worst_group_rate']:>5.1%} "
                  f"{row['mean_coverage']:>6.1%}")
    return out


def score(rows: list[dict]) -> dict:
    pooled = {r["k"]: r for r in rows if r["scheme"] == "pooled"}
    byband = {r["k"]: r for r in rows if r["scheme"] == "by-band"}

    def conc(r):
        return r["concentration"].get(BAND, 0.0)

    series = [(k, conc(pooled[k])) for k in KS]
    rising = all(b >= a - 1e-9 for (_, a), (_, b) in zip(series, series[1:]))

    worst_ok = all(pooled[k]["worst_band"] == BAND for k in KS if k >= 0.5)

    big = pooled[1.0]["group_violation_rate_when_feasible"] or 0.0
    base = pooled[0.0]["group_violation_rate_when_feasible"] or 0.0

    cond_holds, cond_detail = True, {}
    for k in KS:
        r = byband[k]
        cond_detail[k] = {"feasible": r["feasible_trials"],
                          "worst": r["mean_worst_group_rate"]}
        if r["feasible_trials"] > 0 and r["mean_worst_group_rate"] > ALPHA:
            cond_holds = False

    gaps = [(k, (pooled[k]["mean_worst_group_rate"]
                 - byband[k]["mean_worst_group_rate"])) for k in KS]
    widening = gaps[-1][1] > gaps[0][1]

    out = {
        "S1": {"claim": "the shifted band's concentration rises in k",
               "series": series, "held": rising},
        "S2": {"claim": "pooled group-violation above 50% at k = 1.0",
               "at_k1": big, "at_k0": base, "held": big > 0.50},
        "S3": {"claim": f"{BAND} is the worst band at every k >= 0.5",
               "held": worst_ok},
        "S4": {"claim": "conditioning holds the worst band under alpha at "
                        "every feasible k",
               "detail": cond_detail, "held": cond_holds},
        "S5": {"claim": "the pooled-vs-conditioned gap widens with k",
               "gaps": gaps, "held": widening},
    }
    print("\n  S1-S5, scored against addendum eleven")
    for key, v in out.items():
        print(f"  {key}  {'held' if v['held'] else 'MISSED':>6}   "
              f"{v['claim']}")
    return out


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases, base = no-distance fitted scorer")
    print(f"  injecting s -> s^(1/(1+k)) into {BAND} only, k in {KS}")

    t0 = time.time()
    props = injection_properties(cases)
    rows = sweep(cases)
    scored = score(rows)

    payload = {"set": "fine_dev", "band": BAND, "ks": list(KS),
               "alpha": ALPHA, "trials": TRIALS, "seed": SEED,
               "calibration_share": CALIBRATION_SHARE,
               "no_distance_excludes": list(NO_DISTANCE),
               "injection_properties": props,
               "rows": rows, "predictions": scored,
               "elapsed_seconds": round(time.time() - t0, 1)}
    dest = ROOT / "evidence" / "injected_shift.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} "
          f"({payload['elapsed_seconds']}s)")
    (ROOT / "evidence" / "injected_shift.partial.jsonl").unlink(
        missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
