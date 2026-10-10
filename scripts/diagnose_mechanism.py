#!/usr/bin/env python3
"""
Why the lowest-income band absorbs the error budget.

The write-up says "score levels are shifted between bands", which is true and
is not a mechanism. This locates the cause, and rules out the alternative I
expected to find.

CORRECTION, added after addendum five
-------------------------------------
The rejection below tests the wrong population, and the hypothesis it
rejects is substantially right.

It asks what share of **all undetermined states** are amount-only, and finds
31% for `well-below` — not a majority, so the hypothesis looked dead. But the
rule does not meet undetermined states uniformly. It commits on the
**high-scoring** ones, and for `well-below` those are exactly the states where
eligibility is settled (far below the limit) and only the award moves.

Measured on the states the rule actually commits on while undetermined:

    well-below      1,165 unsafe commits,  72% amount-only
    near-threshold    232                  38%
    above             208                   0%
    well-above        385                  20%

**72%, not 31%.** The same selection effect that `calibrate_on_trajectories`
exists to handle — the rule meets a selected population, not the population —
and I walked into it while diagnosing the rule.

Which is confirmed independently by the materiality sweep: removing the spread
criterion entirely drops the concentration from 4.07 to 1.55 and moves the
worst band. If `well-below`'s failures were mostly flips, that could not
happen.

The corrected mechanism is in the README. The original reasoning is kept
below, because a rejection that was itself wrong is worth more visible than
deleted.

The hypothesis I expected, and rejected on the wrong population
---------------------------------------------------------------
Determinability here fires on two conditions: the eligibility verdict flips
across the sweep, **or** the benefit amount moves by more than the materiality
threshold while the verdict is stable. The obvious story was that
`well-below` is dominated by the second — households clearly eligible on
income, whose benefit *amount* still swings with household size — and that the
scorer, which measures distance from the *eligibility* boundary, is blind to
it by construction.

Reconstructed from the complete enumeration (no oracle calls: every swept
household is itself in the benchmark, so its verdict can be looked up), the
shares of undetermined states that are amount-only are

    well-below 31% · near-threshold 42% · above 15% · well-above 14%

`well-below` is not dominated by amount-only undeterminacy, and the band with
the most of it is the one that takes **none** of the budget. The story is
wrong and is recorded here rather than quietly dropped.

What is actually happening
--------------------------
The scorer's one real feature is distance from the eligibility boundary. For
households far **below** the income limit that distance is maximal, so the
scorer is maximally confident — while eligibility still flips for 69% of their
undetermined states, because household size moves both the limit and the
award.

So the failure is not that the scorer ranks badly. It is that its structural
assumption — far from the boundary implies determinable — is **false in one
direction**, and false consistently rather than noisily. A single global
threshold cannot correct a bias that is consistent within a group and
different between groups; a per-group threshold can, because inside a band the
feature's relationship to determinability is at least stable.

Which generalises past this benchmark: a confidence feature encoding "far from
the decision boundary along dimension X" is systematically overconfident on
exactly the cases where a different dimension decides.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.conditional import BANDS, hardness  # noqa: E402
from abstain.evaluate import OPENING  # noqa: E402
from abstain.scorer import FIELDS, features, handcrafted_scorer  # noqa: E402
from abstain.validate import states_of, validate  # noqa: E402

SWEEPABLE = {
    "dependents": [0, 1, 2, 3],
    "employment_income": [0, 9_000, 18_000, 27_000, 36_000],
    "age": [22, 35, 50, 64],
    "state_name": ["NY", "TX", "CA", "MS"],
}


def criterion_split(full_space: list[dict]) -> dict:
    """
    Per band, how many undetermined states flip eligibility rather than only
    moving the amount.

    Every swept household is in the complete enumeration, so its
    full-information verdict is a lookup rather than an engine call.
    """
    verdict = {tuple(c["household"][f] for f in FIELDS):
               c["states"]["|".join(sorted(FIELDS))]["truth"]
               for c in full_space}

    out: dict[str, dict] = {b: {"flip": 0, "amount_only": 0} for b in BANDS}
    for case in full_space:
        hh = case["household"]
        band = hardness(case)
        for r in range(len(FIELDS) + 1):
            for known in itertools.combinations(FIELDS, r):
                if case["states"]["|".join(sorted(known))]["label"] != \
                        "underdetermined":
                    continue
                unknown = [f for f in FIELDS if f not in known]
                seen = set()
                for combo in itertools.product(
                        *[SWEEPABLE[f] for f in unknown]):
                    trial = dict(hh)
                    trial.update(dict(zip(unknown, combo)))
                    seen.add(verdict[tuple(trial[f] for f in FIELDS)])
                key = "flip" if len(seen) > 1 else "amount_only"
                out[band][key] += 1
    return out


def score_profile(cases: list[dict]) -> dict:
    """
    Per band, what the scorer says about states that are undetermined.

    Restricted to states where income is known, because income unknown scores
    zero by construction in every band and would wash out the comparison.
    """
    rows = states_of(cases)
    out: dict[str, dict] = {}
    for band in BANDS:
        sub = [(c, k) for c, k, det in rows
               if hardness(c) == band and not det
               and "employment_income" in k]
        if not sub:
            continue
        scores = sorted(handcrafted_scorer(c, k) for c, k in sub)
        out[band] = {
            "undetermined_states": len(sub),
            "share_scoring_zero": sum(1 for s in scores if s == 0.0)
            / len(sub),
            "median_score": scores[len(scores) // 2],
            "mean_score": sum(scores) / len(scores),
            "mean_log_distance": sum(features(c, k)["log_distance"]
                                     for c, k in sub) / len(sub),
        }
    return out


def level_by_population(cases: list[dict], tau: float = 0.82) -> dict:
    """
    The score level of undecidable states, over the populations that differ.

    `docs/theory.md` §4 argues the subgroup failure comes from score levels
    differing between groups, and cites **0.2106 in `well-below` against
    0.1131 in `near-threshold`**. Those are averages over **every** state in
    the benchmark — and claim 2 of the same document is that the full state
    population is the wrong one, because the rule meets a selected subset.

    So the mechanism's own evidence had the defect the document warns about
    two sections earlier. The conclusion survives and strengthens: over the
    states the rule actually **visits**, the gap is 0.5417 against 0.4012,
    and the ordering across all four bands is unchanged.

    The commit population is reported too and is not usable — at tau = 0.82
    it holds single-digit counts per band — which is worth printing rather
    than leaving a reader to wonder why it was omitted.
    """
    import statistics
    from abstain.rule import run_case

    pops: dict[str, dict[str, list[float]]] = {
        "all_states": {b: [] for b in BANDS},
        "states_visited": {b: [] for b in BANDS},
        "states_committed_at": {b: [] for b in BANDS},
    }

    for c, k, determinable in states_of(cases):
        if not determinable:
            pops["all_states"][hardness(c)].append(handcrafted_scorer(c, k))

    for c in cases:
        b = hardness(c)
        t = run_case(c, handcrafted_scorer, tau)
        known = set(OPENING)
        seq = [frozenset(known)]
        for f in t.asked:
            known.add(f)
            seq.append(frozenset(known))
        for kk in seq:
            st = c["states"]["|".join(sorted(kk))]
            if st["label"] != "determinable":
                pops["states_visited"][b].append(handcrafted_scorer(c, kk))
        if t.committed:
            st = c["states"]["|".join(sorted(seq[-1]))]
            if st["label"] != "determinable":
                pops["states_committed_at"][b].append(
                    handcrafted_scorer(c, seq[-1]))

    out = {"threshold": tau, "set": "fine_dev"}
    for name, by_band in pops.items():
        out[name] = {
            b: {"n": len(v),
                "mean_score": statistics.mean(v) if v else None}
            for b, v in by_band.items()}

    # Per-band AUC over the same two populations, because the published
    # range (0.9345 to 0.9976) is in no evidence file and is from the
    # 79-case `dev` set while every current result uses `fine_dev` -- the
    # two were being quoted in one table without saying which.
    from abstain.scorer import auc

    scored: dict[str, dict] = {"all_states": {}, "states_visited": {}}
    for b in BANDS:
        rows = [(handcrafted_scorer(c, k), d) for c, k, d in states_of(cases)
                if hardness(c) == b]
        scored["all_states"][b] = {"auc": auc(rows), "n": len(rows)}
    for b in BANDS:
        rows = []
        for c in cases:
            if hardness(c) != b:
                continue
            t = run_case(c, handcrafted_scorer, tau)
            known = set(OPENING)
            seq = [frozenset(known)]
            for f in t.asked:
                known.add(f)
                seq.append(frozenset(known))
            for kk in seq:
                st = c["states"]["|".join(sorted(kk))]
                rows.append((handcrafted_scorer(c, kk),
                             st["label"] == "determinable"))
        labels = {d for _, d in rows}
        scored["states_visited"][b] = {
            "auc": auc(rows) if len(labels) > 1 else None, "n": len(rows)}
    out["per_band_auc"] = scored
    return out


def commits_by_criterion(dev: list[dict], full_space: list[dict], *,
                         alpha: float = 0.20, trials: int = 40,
                         seed: int = 71) -> dict:
    """
    The same question, asked of the states the rule actually commits on.

    This is the correction. Asking it of all undetermined states gives 31%
    for `well-below` and the hypothesis looks dead; asking it of the states
    the rule selects gives 72% and it is substantially right.

    The rule commits on the HIGH-SCORING states, and for `well-below` those
    are exactly the ones where eligibility is settled and only the award
    moves. Same selection effect `calibrate_on_trajectories` exists to
    handle.
    """
    verdict = {tuple(c["household"][f] for f in FIELDS):
               c["states"]["|".join(sorted(FIELDS))]["truth"]
               for c in full_space}
    by_id = {c["id"]: c for c in dev}
    captured: list[tuple] = []

    def spy(cal, result, dep_cases):
        for row in result.detail:
            if row["outcome"] == "unsafe":
                captured.append((row["case"],
                                 tuple(sorted(set(OPENING) | set(row["asked"])))))

    validate(dev, handcrafted_scorer, alpha=alpha, trials=trials, seed=seed,
             calibration_share=0.30, on_trial=spy)

    out: dict[str, dict] = {b: {"flip": 0, "amount_only": 0} for b in BANDS}
    for cid, known in captured:
        case = by_id[cid]
        unknown = [f for f in FIELDS if f not in known]
        seen = set()
        for combo in itertools.product(*[SWEEPABLE[f] for f in unknown]):
            trial = dict(case["household"])
            trial.update(dict(zip(unknown, combo)))
            seen.add(verdict[tuple(trial[f] for f in FIELDS)])
        key = "flip" if len(seen) > 1 else "amount_only"
        out[hardness(case)][key] += 1
    return out


def main() -> int:
    full = json.loads((ROOT / "evidence" / "cases_fine.json").read_text())
    dev = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())

    print("  The hypothesis that was wrong")
    print("  " + "-" * 70)
    print("  If well-below failed because the benefit AMOUNT moves while")
    print("  eligibility is settled, it would be mostly amount-only.\n")
    crit = criterion_split(full)
    print(f"  {'band':>16} {'undetermined':>13} {'elig flips':>11} "
          f"{'amount only':>12}")
    for b in BANDS:
        d = crit[b]
        tot = d["flip"] + d["amount_only"]
        print(f"  {b:>16} {tot:>13} {d['flip']:>11} "
              f"{d['amount_only']:>7} ({d['amount_only'] / tot:>3.0%})")
    print("\n  It is not -- on THIS population. But the rule does not meet")
    print("  undetermined states uniformly; it commits on the high-scoring")
    print("  ones. Asked of the states it actually commits on:\n")

    commits = commits_by_criterion(dev, full)
    print(f"  {'band':>16} {'unsafe commits':>15} {'flip':>7} "
          f"{'amount only':>12}")
    for b in BANDS:
        d = commits[b]
        tot = d["flip"] + d["amount_only"]
        if not tot:
            continue
        print(f"  {b:>16} {tot:>15} {d['flip']:>7} "
              f"{d['amount_only']:>7} ({d['amount_only'] / tot:>3.0%})")
    wb = commits["well-below"]
    share = wb["amount_only"] / (wb["flip"] + wb["amount_only"])
    print(f"\n  {share:.0%} for well-below, not 31%. The hypothesis was")
    print("  rejected on the wrong population, and is substantially right.\n")

    print("  What the scorer actually does")
    print("  " + "-" * 70)
    prof = score_profile(dev)
    print(f"  {'band':>16} {'undet states':>13} {'score==0':>9} "
          f"{'median':>8} {'mean dist':>10}")
    for b in BANDS:
        if b not in prof:
            continue
        d = prof[b]
        print(f"  {b:>16} {d['undetermined_states']:>13} "
              f"{d['share_scoring_zero']:>8.0%} {d['median_score']:>8.4f} "
              f"{d['mean_log_distance']:>10.4f}")

    wb = crit["well-below"]
    flip_share = wb["flip"] / (wb["flip"] + wb["amount_only"])
    print("\n  Not one undetermined well-below state scores zero, and their")
    print("  median score is the highest of any band. The scorer's one real")
    print("  feature is distance from the eligibility boundary, which is")
    print("  maximal for households far BELOW the limit -- while eligibility")
    print(f"  still flips for {flip_share:.0%} of their undetermined states.")

    levels = level_by_population(dev)

    print("\n  undecidable-state score level, by population")

    print(f"  {'band':>16} {'all':>9} {'visited':>9} {'committed':>11}")

    for b in BANDS:

        def _f(key):

            v = levels[key][b]['mean_score']

            return '--' if v is None else f'{v:.4f}'

        print(f"  {b:>16} {_f('all_states'):>9} "

              f"{_f('states_visited'):>9} "

              f"{_f('states_committed_at'):>11}")


    payload = {
        "level_by_population": levels,
        "criterion_split": crit,
        "criterion_split_of_commits": commits,
        "score_profile": prof,
        "correction": (
            "Asked of ALL undetermined states, well-below is 31% amount-only "
            "and the hypothesis looked rejected. Asked of the states the rule "
            "actually commits on, it is 72% and the hypothesis is "
            "substantially right. The rule meets a selected population."),
    }
    dest = ROOT / "evidence" / "mechanism.json"
    dest.write_text(json.dumps(payload, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
