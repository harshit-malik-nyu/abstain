#!/usr/bin/env python3
"""
Round R — pool-level uncertainty for the figure this repository quotes most.

`docs/preregistration-5.md`, addendum ten, committed before this file existed.
B, the trial count, α and the root seed are fixed there and none is adjusted
after seeing a result.

What is being measured, and why the existing interval is not enough
-------------------------------------------------------------------
`group_violation_rate_when_feasible` is the fraction of trials in which some
income band exceeded α. At α = 0.20 it is ~98% pooled and ~3% by band, and
that pair is the most load-bearing comparison in the repository.

Round O gave it an exact Clopper-Pearson interval and said what the interval
conditions away: each trial is an independent split of a **fixed** pool, so
the interval is exact for splits of *these* 672 cases and silent about the
pool. For the across-trial band rates that same gap is the difference between
±0.6 and ±9.5 points — `conditional.bootstrap_band_rate` exists precisely
because the narrow version overstates precision sixteen-fold.

So: resample the 672 cases with replacement, run both arms on the resampled
pool, and take percentiles over draws.

Two honest limitations, both fixed in the pre-registration
----------------------------------------------------------
**100 trials per draw, not 200.** Cost is B × trials. The consequence is that
the width below contains pool variability *and* Monte Carlo error at 100
trials, so it is an **upper** estimate of the pool-only width. Conservative,
and stated in advance.

**Resampling duplicates cases**, so a calibration fold can hold the same
household twice. That is what a bootstrap is, and what `bootstrap_band_rate`
already does here, so it is existing practice rather than a new liberty.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from abstain.group import (trial_rate_interval,  # noqa: E402
                           validate_groups)
from abstain.scorer import handcrafted_scorer  # noqa: E402

ALPHA = 0.20
DRAWS = 40
TRIALS = 100
ROOT_SEED = 101
CALIBRATION_SHARE = 0.30
SCHEMES = ("pooled", "by-band")
LEVEL = 0.95


def resample(cases: list[dict], rng: random.Random) -> list[dict]:
    """
    A bootstrap pool of the same size, drawn with replacement.

    Case ids are rewritten so that duplicates are distinct to the evaluation
    loop. Without this, `collector`'s `by_id` map and the per-case tally
    would silently merge a duplicated household into one entry — the pool
    would be 672 draws and the breakdown would see fewer, which would shrink
    the very variance this round exists to measure.
    """
    out = []
    for i in range(len(cases)):
        c = dict(rng.choice(cases))
        c["id"] = i
        out.append(c)
    return out


def one_draw(cases: list[dict], seed: int) -> dict:
    """Both arms on one resampled pool, paired on the same pool."""
    pool = resample(cases, random.Random(seed))
    row: dict = {"seed": seed}
    for scheme in SCHEMES:
        v = validate_groups(pool, handcrafted_scorer, scheme=scheme,
                            alpha=ALPHA, trials=TRIALS, seed=seed,
                            calibration_share=CALIBRATION_SHARE)
        d = v.as_dict()
        row[scheme] = {
            "group_violation_rate_when_feasible":
                d["group_violation_rate_when_feasible"],
            "feasible_trials": d["feasible_trials"],
            "mean_worst_group_rate": d["mean_worst_group_rate"],
            "mean_coverage": d["mean_coverage"],
        }
    return row


def percentile_interval(values: list[float],
                        level: float = LEVEL) -> tuple[float, float]:
    """
    The empirical percentile interval over bootstrap draws.

    A percentile interval rather than a normal approximation because these
    rates sit near 1.0 and 0.0, where a symmetric interval runs off the end
    of the scale and has to be clipped — and a clipped interval is a
    different statement from a quantile.

    The index arithmetic is worth stating because the first version got it
    wrong in a way that looked right. It computed `int(tail * B) - 1` and
    `int((1 - tail) * B)`, which at B = 40 returns the **minimum and
    maximum** rather than the 2.5th and 97.5th percentiles. That is not
    obviously a bug, because [min, max] over B draws has coverage
    (B − 1)/(B + 1) — 95.1% at B = 40, almost exactly the level asked for.
    It would have been a coincidence standing in for a calculation, and it
    would have broken silently at any other B.

    So the quantile is computed on the `len − 1` spacing, which is the
    standard empirical quantile and is right at every B.
    """
    xs = sorted(values)
    if not xs:
        return (0.0, 1.0)
    if len(xs) == 1:
        return (xs[0], xs[0])
    tail = (1.0 - level) / 2.0
    last = len(xs) - 1
    lo_i = max(0, round(tail * last))
    hi_i = min(last, round((1.0 - tail) * last))
    return (xs[lo_i], xs[hi_i])


def main() -> int:
    cases = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    print(f"  fine_dev: {len(cases)} cases")
    print(f"  {DRAWS} bootstrap draws x {TRIALS} trials, alpha = {ALPHA}, "
          f"root seed {ROOT_SEED}")
    print("  resampling CASES with replacement; ids rewritten so duplicates "
          "stay distinct\n")

    t0 = time.time()

    # Checkpointed per draw.
    #
    # The first attempt at this round was killed at draw 32 of 40 by the
    # session it was running in, losing half an hour of work that was already
    # computed. Each draw is a pure function of its seed, so appending them to
    # a JSONL as they finish costs nothing and makes an interruption cost one
    # draw instead of all of them. Round four hit the same thing on the
    # holdout and the response there was a verifier; this is the cheaper half
    # of the same lesson.
    ckpt = ROOT / "evidence" / "pool_bootstrap.partial.jsonl"
    done: dict[int, dict] = {}
    if ckpt.exists():
        for line in ckpt.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done[r["seed"]] = r
        print(f"  resuming: {len(done)} draw(s) already in "
              f"{ckpt.name}\n")

    rows = []
    for b in range(DRAWS):
        seed = ROOT_SEED + b
        if seed in done:
            row = done[seed]
            mark = "  (cached)"
        else:
            row = one_draw(cases, seed)
            with ckpt.open("a") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            mark = ""
        rows.append(row)
        p, g = row["pooled"], row["by-band"]
        pv = p["group_violation_rate_when_feasible"]
        gv = g["group_violation_rate_when_feasible"]
        print(f"  draw {b + 1:>2}/{DRAWS}  pooled "
              f"{'n/a' if pv is None else f'{pv:>6.1%}'}  "
              f"by-band {'n/a' if gv is None else f'{gv:>6.1%}'}  "
              f"(feasible {p['feasible_trials']:>3} / "
              f"{g['feasible_trials']:>3}){mark}")

    out: dict = {"alpha": ALPHA, "draws": DRAWS, "trials_per_draw": TRIALS,
                 "root_seed": ROOT_SEED,
                 "calibration_share": CALIBRATION_SHARE,
                 "level": LEVEL, "rows": rows}

    print("\n  pool-level percentile intervals, and the exact interval they "
          "are being compared against")
    summary = {}
    for scheme in SCHEMES:
        vals = [r[scheme]["group_violation_rate_when_feasible"]
                for r in rows
                if r[scheme]["group_violation_rate_when_feasible"] is not None]
        feas = [r[scheme]["feasible_trials"] for r in rows]
        lo, hi = percentile_interval(vals)
        mean = statistics.fmean(vals) if vals else 0.0

        # The conditional interval this is being set against: the same rate
        # measured once on the real pool, at the same trial count.
        base = validate_groups(cases, handcrafted_scorer, scheme=scheme,
                               alpha=ALPHA, trials=TRIALS, seed=ROOT_SEED,
                               calibration_share=CALIBRATION_SHARE).as_dict()
        b_rate = base["group_violation_rate_when_feasible"]
        b_n = base["feasible_trials"]
        e_lo, e_hi = trial_rate_interval(round((b_rate or 0.0) * b_n), b_n)

        summary[scheme] = {
            "draws_usable": len(vals), "mean": mean,
            "pool_interval": [lo, hi], "pool_width": hi - lo,
            "exact_point": b_rate, "exact_interval": [e_lo, e_hi],
            "exact_width": e_hi - e_lo,
            "feasible_min": min(feas), "feasible_max": max(feas),
            "feasible_varies": min(feas) != max(feas),
        }
        print(f"\n  {scheme}")
        print(f"    pool-level   mean {mean:>6.1%}   "
              f"95% [{lo:>6.1%}, {hi:>6.1%}]   width {hi - lo:>6.1%}")
        print(f"    exact (fixed pool) {b_rate if b_rate is None else f'{b_rate:>6.1%}'}"
              f"   95% [{e_lo:>6.1%}, {e_hi:>6.1%}]   "
              f"width {e_hi - e_lo:>6.1%}")
        print(f"    feasible trials across draws: "
              f"{min(feas)} to {max(feas)}")

    p_lo, p_hi = summary["pooled"]["pool_interval"]
    g_lo, g_hi = summary["by-band"]["pool_interval"]
    wider = any(summary[s]["pool_width"] > summary[s]["exact_width"]
                for s in SCHEMES)
    scored = {
        "R1": {"claim": "pooled interval entirely above 90%",
               "interval": [p_lo, p_hi], "held": p_lo > 0.90},
        "R2": {"claim": "by-band interval entirely below 20%",
               "interval": [g_lo, g_hi], "held": g_hi < 0.20},
        "R3": {"claim": "the two intervals do not overlap",
               "held": g_hi < p_lo or p_hi < g_lo},
        "R4": {"claim": "the pool interval is wider than the exact one for "
                        "at least one arm",
               "widths": {s: [summary[s]["pool_width"],
                              summary[s]["exact_width"]] for s in SCHEMES},
               "held": wider},
        "R5": {"claim": "by-band feasibility varies across draws",
               "range": [summary["by-band"]["feasible_min"],
                         summary["by-band"]["feasible_max"]],
               "held": summary["by-band"]["feasible_varies"]},
    }
    print("\n  R1-R5, scored against addendum ten")
    for k, v in scored.items():
        print(f"  {k}  {'held' if v['held'] else 'MISSED':>6}   {v['claim']}")

    out["summary"] = summary
    out["predictions"] = scored
    out["elapsed_seconds"] = round(time.time() - t0, 1)
    dest = ROOT / "evidence" / "pool_bootstrap.json"
    dest.write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"\n  wrote {dest.relative_to(ROOT)} ({out['elapsed_seconds']}s)")

    # The checkpoint has served its purpose once the real output exists, and
    # leaving it would invite a later run to resume from a stale half of a
    # superseded experiment.
    ckpt.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
