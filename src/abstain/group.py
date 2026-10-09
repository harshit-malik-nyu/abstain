"""
One threshold per group, instead of one threshold.

What this fixes
---------------
`conditional.py` measured where the error budget actually goes, and it does
not go where the pooled number suggests. On dev at α = 0.20 the pooled unsafe
rate is 5.6% and the lowest-income band's is 19.2% — 3.44 times its
proportional share, while the band predicted to fail took none at all.

The diagnosis is in `docs/preregistration-3.md` and is worth restating because
it determines the fix. The scorer's *ordering* is nearly perfect inside every
band (per-band AUC 0.93 to 0.998). What differs is where the score *levels*
sit: undetermined states average 0.21 in `well-below` and 0.11 in
`near-threshold`. One global threshold is a single horizontal line drawn
across four vertically shifted distributions, so it cuts each one at a
different quantile — tight where the distribution sits low, loose where it
sits high.

A better-*ranking* scorer does not fix that, and the measurement is sharper
than the argument: across three scorers on `fine_dev`, AUC descends 0.9555 →
0.9252 → 0.8888 while the concentration descends with it, 4.13 → 3.31 → 1.72.
On this benchmark the **worst**-ranking scorer spent its budget most evenly.

Two things do fix it, and this docstring claimed only one for two rounds.

**Calibrating inside each group** — what this module does. It converts the
per-group rate into a *certificate*: each group is tested against the §1 bound
at level δ, so a group that cannot be certified makes the arm infeasible
rather than quietly unsafe.

**Removing a feature that is directionally wrong for one group** — measured in
round J. I had pre-registered that it would not work at all (J1) and it is the
cheapest remedy here.

The two are not interchangeable, and the difference is the whole point of this
module. Conditioning **guarantees** a per-group rate at level δ: a group that
cannot be certified makes the arm infeasible instead of quietly unsafe. A
pooled rule over a better-behaved score **happens to come in** under budget
per group, which is a measurement rather than a statement.

Round O measured how much that distinction is worth, and it is worth more than
the first version of this docstring implied. Trials in which some band exceeded
α, out of 200 on `fine_dev`:

    alpha   handcrafted+cond      no-distance pooled    both
    0.20    2.6% [0.8, 5.9]/196  2.5% [0.8,  5.7]/200  1.1%/187
    0.15    8.3% [4.1, 14.8]/120 24.5% [18.7,31.1]/200 4.0%/ 99
    0.10    0.0% [0.0, 70.8]/  3 26.0% [20.1,32.7]/200   -- /  0

Exact 95% intervals from `trial_rate_interval`, and two cells need them: at
alpha 0.20 the first two columns are indistinguishable rather than ranked, and
the 0.0% at alpha 0.10 is zero failures in THREE trials with an upper bound of
70.8%.

Removing the feature matches conditioning at α = 0.20 and is three times worse
at α = 0.15. Together they beat either alone wherever both are feasible. And at
α = 0.10 on 672 cases nothing is available: conditioning is infeasible in every
trial for both scorers, so there is no per-group certificate to buy at any
price.

Note that the pooled across-trial rate tells a gentler story than the per-trial
one — 12.48% worst band at α = 0.20 against 2.5% of trials failing, but 11.65%
against **24.5%** at α = 0.15. Both are honest; one averages over trials and
the other counts failures. Quoting only the first is how "removing the feature
brings every band inside the budget" got written, and it was false of a quarter
of deployments.

So: audit the features first, because it is cheap and it is the only remedy
available at tight tolerances — then condition as well, because they are
complements and because only one of them gives you a statement rather than an
outcome.

Prior work, named
-----------------
This is **Mondrian conformal prediction** — Vovk and colleagues, mid-2000s —
and group-conditional coverage has been studied in the conformal literature
since. The construction is not a contribution of this repository and is not
presented as one.

What is contributed is the measurement: on a benchmark where the subgroup
failure is real and has a distributional consequence, what does group
conditioning cost, and at what calibration size does it become affordable?
The second question has a closed-form answer and `minimum_calibration_size`
below gives it, because that is the number an operator can act on.

The cost, which is not small
----------------------------
Partitioning calibration data by group divides n by the number of groups, and
a Clopper–Pearson bound with zero observed failures in n trials is still
1 − δ^(1/n). So the tightest tolerance reachable at all, at δ = 0.05:

    7 cases per group  ->  34.8%
   10 cases per group  ->  25.9%
   20 cases per group  ->  13.9%
   29 cases per group  ->   9.8%

Every cell is `reachable_alpha(n)` and a test now requires it to be, because
the last row read 9.9% for a value of 9.81% — a hand-typed figure sitting
beside the code that computes it.

Dev's 60% calibration fold is 47 cases, about 11 per band. Group conditioning
at a 10% tolerance is arithmetically out of reach there, and no amount of
implementation care changes it. That is the honest shape of this trade: the
pooled rule is feasible and conditionally misleading, the group-conditional
rule is conditionally honest and mostly infeasible, and the way out is more
calibration data rather than a cleverer rule.

Both are therefore reported, at the same tolerances, with the infeasibility
rate in the same table as the coverage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .conditional import BANDS, hardness
from .rule import INFEASIBLE_THRESHOLD, clopper_pearson_upper, run_case

# ---------------------------------------------------------------------------
# Grouping schemes
# ---------------------------------------------------------------------------


def by_band(case: dict) -> str:
    """Full group conditioning: the four income bands."""
    return hardness(case)


def pooled(case: dict) -> str:
    """One group. The pooled rule, expressed in the same interface."""
    return "all"


def separate_well_below(case: dict) -> str:
    """
    Two groups: the band that failed, and everything else.

    **Post-hoc.** `well-below` is separated because experiment C showed
    `well-below` failing, which is selection on the outcome. A scheme chosen
    after seeing which group fails is fitted to this benchmark and its
    apparent success does not transfer to a deployment whose failing group is
    different.

    It is here because the comparison is informative — two groups cost half
    the calibration data four groups cost — and it is labelled rather than
    quietly reported next to the pre-specified schemes. `by_band` is the rule
    a practitioner should use, because it requires no knowledge of which
    group will fail.
    """
    return "well-below" if hardness(case) == "well-below" else "rest"


SCHEMES = {"pooled": pooled, "by-band": by_band,
           "separate-well-below": separate_well_below}

POST_HOC = frozenset({"separate-well-below"})


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def minimum_calibration_size(alpha: float, delta: float = 0.05) -> int:
    """
    Fewest calibration cases per group that can reach `alpha` at all.

    Closed form, not a search. With zero observed failures in n the
    Clopper–Pearson upper bound is 1 − δ^(1/n), so the requirement
    1 − δ^(1/n) ≤ α rearranges to

        n >= ln(delta) / ln(1 - alpha)

    This is a hard floor and it is worth knowing before collecting data
    rather than after: it depends on neither the scorer nor the benchmark,
    only on the tolerance and the confidence level. An operator who wants a
    10% tolerance per group at 95% confidence needs 29 calibration cases in
    *every* group, whatever else they do.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")
    if not 0.0 < delta < 1.0:
        raise ValueError(f"delta must be in (0, 1), got {delta}")
    return math.ceil(math.log(delta) / math.log(1.0 - alpha))


@dataclass
class GroupCalibration:
    """
    A threshold per group, and whether every group got one.

    `feasible` is **conjunctive**: if any group failed to find a threshold,
    the whole calibration failed. A rule that holds the tolerance in three
    groups and not the fourth does not hold the tolerance, and reporting it as
    a partial success would reintroduce exactly the averaging this module
    exists to remove.
    """

    alpha: float
    delta: float
    thresholds: dict[str, float] = field(default_factory=dict)
    per_group: dict[str, dict] = field(default_factory=dict)
    scheme: str = "by-band"

    @property
    def feasible(self) -> bool:
        return bool(self.per_group) and all(
            g["feasible"] for g in self.per_group.values())

    @property
    def groups_feasible(self) -> int:
        return sum(1 for g in self.per_group.values() if g["feasible"])

    def threshold_for(self, case: dict) -> float:
        """
        The deployed threshold for one case.

        A group absent from calibration — no calibration case fell in it —
        gets the refusal threshold, not the pooled one. Falling back to a
        threshold calibrated on other groups is precisely the substitution
        that produced the 19.2% band, and doing it silently in the module
        written to fix that would be worse than not writing it.
        """
        return self.thresholds.get(SCHEMES[self.scheme](case),
                                   INFEASIBLE_THRESHOLD)

    def as_dict(self) -> dict:
        return {"scheme": self.scheme, "alpha": self.alpha,
                "delta": self.delta, "feasible": self.feasible,
                "groups_feasible": self.groups_feasible,
                "groups": len(self.per_group),
                "thresholds": dict(self.thresholds),
                "per_group": self.per_group,
                "post_hoc": self.scheme in POST_HOC}


def calibrate_by_group(cases: list[dict], scorer, *, scheme: str = "by-band",
                       alpha: float = 0.05, delta: float = 0.05,
                       grid: int = 101, budget: int = 4) -> GroupCalibration:
    """
    Run the trajectory calibration separately inside each group.

    Same construction as `calibrate_on_trajectories` — the calibration unit
    is the deployed unit, for the same reason — applied within each group's
    own cases. Reusing that function rather than reimplementing the search is
    deliberate: a difference between the pooled and grouped results should be
    attributable to the grouping and not to two copies of a threshold sweep
    drifting apart.

    `delta` is **not** split across groups. Each group's bound is a separate
    statement at level δ about that group, which is what group-conditional
    validity means. A simultaneous statement over all groups at once would
    need δ/|groups| and would be more conservative still; the per-group form
    is the one the literature uses and the one an operator asking "is this
    safe for this applicant" wants.
    """
    if scheme not in SCHEMES:
        raise ValueError(f"unknown scheme: {scheme!r}")
    key = SCHEMES[scheme]

    buckets: dict[str, list[dict]] = {}
    for c in cases:
        buckets.setdefault(key(c), []).append(c)

    cal = GroupCalibration(alpha=alpha, delta=delta, scheme=scheme)

    for group, group_cases in sorted(buckets.items()):
        # Imported here rather than at module scope: `rule` does not import
        # this module and keeping it that way means the dependency runs one
        # direction only.
        from .rule import calibrate_on_trajectories
        c = calibrate_on_trajectories(
            group_cases, scorer,
            lambda cs, sc, tau: run_case(cs, sc, tau, budget=budget),
            alpha=alpha, delta=delta, grid=grid)
        cal.thresholds[group] = c.threshold
        cal.per_group[group] = c.as_dict() | {
            "n_cases": len(group_cases),
            "minimum_needed": minimum_calibration_size(alpha, delta),
            "enough_data": len(group_cases) >= minimum_calibration_size(
                alpha, delta)}

    return cal


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

@dataclass
class GroupResult:
    scheme: str
    """How calibration was partitioned."""

    alpha: float
    n: int = 0
    measured_by: str = "by-band"
    """How the results are broken down. Separate from `scheme` on purpose —
    see `evaluate_by_group`."""

    unsafe: int = 0
    resolved: int = 0
    abstained: int = 0
    decidable: int = 0
    questions: int = 0
    by_group: dict[str, dict] = field(default_factory=dict)

    @property
    def unsafe_rate(self) -> float:
        return self.unsafe / self.n if self.n else 0.0

    @property
    def coverage(self) -> float:
        return self.resolved / self.decidable if self.decidable else 0.0

    @property
    def questions_per_case(self) -> float:
        return self.questions / self.n if self.n else 0.0

    @property
    def worst_group_rate(self) -> float:
        """
        The highest unsafe rate in any deployed group.

        The number this module exists to move. A pooled rate inside budget
        with a group outside it is the failure being fixed, so the summary
        carries the maximum rather than only the mean.
        """
        seen = [g for g in self.by_group.values() if g["deployed"]]
        return max((g["unsafe"] / g["deployed"] for g in seen), default=0.0)

    @property
    def max_concentration(self) -> float:
        """Highest ratio of a group's unsafe share to its deployed share."""
        if not self.unsafe or not self.n:
            return 0.0
        out = 0.0
        for g in self.by_group.values():
            if not g["deployed"]:
                continue
            out = max(out, (g["unsafe"] / self.unsafe)
                      / (g["deployed"] / self.n))
        return out

    def as_dict(self) -> dict:
        return {"scheme": self.scheme, "measured_by": self.measured_by,
                "alpha": self.alpha, "n": self.n,
                "unsafe_rate": self.unsafe_rate, "coverage": self.coverage,
                "questions_per_case": self.questions_per_case,
                "worst_group_rate": self.worst_group_rate,
                "max_concentration": self.max_concentration,
                "by_group": self.by_group}


def evaluate_by_group(cases: list[dict], scorer, cal: GroupCalibration,
                      budget: int = 4, measure_by: str = "by-band"
                      ) -> GroupResult:
    """
    Deploy, judging each case against its own group's threshold.

    Outcome labels follow `evaluate.py` exactly — committed-while-undetermined
    is unsafe, whatever verdict came out — so the two paths cannot disagree
    about what "unsafe" means.

    `measure_by` is separate from `cal.scheme`, and it has to be
    ------------------------------------------------------------
    The calibration partition decides which threshold a case is judged
    against. The **measurement** partition decides how the results are broken
    down. The first version used one parameter for both, and that silently
    inverted the comparison the module exists to make.

    Under `scheme="pooled"` there is a single group, so bucketing the results
    by the calibration partition gave one bucket: `worst_group_rate` returned
    the pooled rate and `max_concentration` was 1.00 by definition. The
    reported numbers at alpha = 0.20 were a worst group of 11.1% and a
    concentration of 1.00 for the pooled rule, against 12.9% and 1.80 for the
    grouped one — which reads as the grouped rule being *worse* on exactly
    the axis it was built to improve.

    The real figure for the pooled rule, measured on bands, is **45.7%** in
    `well-below` against a 20% budget. Measured consistently, group
    conditioning takes the worst band from 45.7% to 12.9%.

    So the two partitions are now separate arguments, and `measure_by`
    defaults to the bands regardless of how calibration was grouped. A
    comparison between grouping schemes is only a comparison if every scheme
    is scored against the same partition.
    """
    from .evaluate import OPENING, ever_decidable, final_truth

    if measure_by not in SCHEMES:
        raise ValueError(f"unknown measurement partition: {measure_by!r}")

    r = GroupResult(scheme=cal.scheme, alpha=cal.alpha, n=len(cases),
                    measured_by=measure_by)
    key = SCHEMES[measure_by]

    for case in cases:
        group = key(case)
        g = r.by_group.setdefault(group, {
            "deployed": 0, "unsafe": 0, "resolved": 0, "abstained": 0,
            "decidable": 0, "questions": 0,
            # The threshold this case was actually judged against, which comes
            # from the CALIBRATION partition. Looking it up by the measurement
            # group would be wrong whenever the two differ.
            "threshold": cal.threshold_for(case)})

        g["deployed"] += 1
        decidable = ever_decidable(case)
        if decidable:
            r.decidable += 1
            g["decidable"] += 1

        t = run_case(case, scorer, cal.threshold_for(case), budget=budget,
                     opening=OPENING)
        r.questions += t.questions
        # Per band, because the central mechanistic claim is that a single
        # global threshold mis-allocates QUESTIONS and not only risk. That
        # claim was inferred from safety and coverage moving together; this
        # is what measures it.
        g["questions"] += t.questions
        truth = final_truth(case, frozenset(set(OPENING) | set(t.asked)))

        if not t.committed:
            r.abstained += 1
            g["abstained"] += 1
        elif truth == "cannot_determine":
            r.unsafe += 1
            g["unsafe"] += 1
        else:
            r.resolved += 1
            g["resolved"] += 1

    return r


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class GroupValidation:
    """
    Repeated calibrate-and-deploy under one grouping scheme.

    Carries the same feasibility discipline as `Validation`: the guarantee is
    conditional on calibration reporting feasible, so the headline rate is
    computed over feasible trials and is `None` when there were none.
    """

    scheme: str
    alpha: float
    delta: float
    measured_by: str = "by-band"
    trials: int = 0
    feasible_trials: int = 0
    violations: int = 0
    violations_when_feasible: int = 0
    group_violations: int = 0
    coverage_sum: float = 0.0
    questions_sum: float = 0.0
    worst_sum: float = 0.0
    concentration_sum: float = 0.0
    post_hoc: bool = False
    bands: dict[str, dict] = field(default_factory=dict)
    """
    Per-band counts, pooled over feasible trials.

    Added because the summary could not answer the question the fix has to
    answer. A scheme that drives the worst band's unsafe rate down by
    **abstaining on that band** has not fixed anything — it has moved the harm
    from wrong decisions to no decisions, and for `well-below`, the
    lowest-income households, that is a different harm rather than a smaller
    one.

    Safety and coverage therefore have to be read together *per band*, not
    pooled. `mean_coverage` alone would hide a scheme that resolves 90% of the
    three comfortable bands and 0% of the one that was failing.
    """

    def tally(self, band: str) -> dict:
        if band not in self.bands:
            self.bands[band] = {"deployed": 0, "unsafe": 0, "resolved": 0,
                                "abstained": 0, "decidable": 0,
                                "questions": 0}
        return self.bands[band]

    @property
    def band_table(self) -> list[dict]:
        """Unsafe rate and coverage side by side, per band."""
        out = []
        for band, t in sorted(self.bands.items()):
            out.append({
                "band": band,
                "deployed": t["deployed"],
                "unsafe": t["unsafe"],
                "unsafe_rate": (t["unsafe"] / t["deployed"]
                                if t["deployed"] else 0.0),
                "coverage": (t["resolved"] / t["decidable"]
                             if t["decidable"] else 0.0),
                "abstention_rate": (t["abstained"] / t["deployed"]
                                    if t["deployed"] else 0.0),
                "questions_per_case": (t["questions"] / t["deployed"]
                                       if t["deployed"] else 0.0),
            })
        return out

    @property
    def worst_band_overall(self) -> str | None:
        rows = [r for r in self.band_table if r["deployed"]]
        if not rows:
            return None
        return max(rows, key=lambda r: r["unsafe_rate"])["band"]

    @property
    def min_band_coverage(self) -> float:
        """
        The least-served band's coverage.

        The number that catches a scheme buying safety with denial of
        service. A pooled coverage of 80% is compatible with one band at
        zero, and if that band is the one the scheme was built to protect,
        the fix is not a fix.
        """
        rows = [r for r in self.band_table if r["deployed"]]
        return min((r["coverage"] for r in rows), default=0.0)

    @property
    def infeasible_rate(self) -> float:
        return ((self.trials - self.feasible_trials) / self.trials
                if self.trials else 0.0)

    @property
    def violation_rate_when_feasible(self) -> float | None:
        if not self.feasible_trials:
            return None
        return self.violations_when_feasible / self.feasible_trials

    @property
    def group_violation_rate_when_feasible(self) -> float | None:
        """
        Share of feasible trials where **any group** exceeded alpha.

        The quantity D1 is about, and strictly harder to satisfy than the
        pooled rate: a trial passes only if every deployed group is inside
        budget. The pooled rule is expected to fail this often while passing
        the pooled check, which is the whole finding restated as a number.
        """
        if not self.feasible_trials:
            return None
        return self.group_violations / self.feasible_trials

    def _mean(self, total: float) -> float:
        return total / self.feasible_trials if self.feasible_trials else 0.0

    def as_dict(self) -> dict:
        return {
            "scheme": self.scheme, "measured_by": self.measured_by,
            "alpha": self.alpha, "delta": self.delta,
            "trials": self.trials, "feasible_trials": self.feasible_trials,
            "infeasible_rate": self.infeasible_rate,
            "violation_rate_when_feasible": self.violation_rate_when_feasible,
            "group_violation_rate_when_feasible":
                self.group_violation_rate_when_feasible,
            "mean_coverage": self._mean(self.coverage_sum),
            "min_band_coverage": self.min_band_coverage,
            "worst_band": self.worst_band_overall,
            "bands": self.band_table,
            "mean_questions": self._mean(self.questions_sum),
            "mean_worst_group_rate": self._mean(self.worst_sum),
            "mean_max_concentration": self._mean(self.concentration_sum),
            "post_hoc": self.post_hoc,
        }


def validate_groups(cases: list[dict], scorer, *, scheme: str = "by-band",
                    alpha: float = 0.05, delta: float = 0.05,
                    trials: int = 150, seed: int = 23,
                    calibration_share: float = 0.6,
                    calibration_size: int | None = None,
                    measure_by: str = "by-band",
                    refit=None) -> GroupValidation:
    """
    The same experiment as `validate`, with the grouping scheme varied.

    `refit`, and the experiment that was silently wrong without it
    -------------------------------------------------------------
    Pass a callable taking the fitting cases and returning a scorer, and each
    trial trains a fresh one on a fold disjoint from both calibration and
    deployment — the same three-fold protocol `validate.refit` enforces, for
    the same reason: a scorer fit on the calibration or deployment data
    violated a 5% target in 35.8% of trials when this project measured it.

    This did not exist until an experiment needed it, and its absence was not
    an inconvenience but a wrong answer. Addendum two asked whether group
    conditioning fixes the subgroup failure **for a learned scorer**; with no
    way to refit here, that arm passed the handcrafted scorer instead and
    produced a table that looked like an answer and was a duplicate of an
    earlier result. Nothing failed and nothing warned. A missing capability
    that quietly changes which question is being answered is worse than one
    that raises an error.

    Uses `validate.trial_split` rather than its own draw, so the pooled and
    grouped arms see **identical** calibration and deployment sets in every
    trial. That makes the comparison paired: a difference between schemes
    cannot be a difference in which cases they happened to get, which at 79
    cases and four bands would otherwise be a real possibility.
    """
    from .validate import trial_split

    v = GroupValidation(scheme=scheme, alpha=alpha, delta=delta,
                        measured_by=measure_by,
                        post_hoc=scheme in POST_HOC)

    for t in range(trials):
        fit_cases, cal_cases, dep_cases = trial_split(
            cases, trial=t, seed=seed,
            calibration_share=calibration_share,
            calibration_size=calibration_size, refit=refit)
        if not cal_cases or not dep_cases:
            continue

        active = scorer
        if refit is not None:
            if not fit_cases:
                continue
            active = refit(fit_cases)

        cal = calibrate_by_group(cal_cases, active, scheme=scheme,
                                 alpha=alpha, delta=delta)
        res = evaluate_by_group(dep_cases, active, cal,
                                measure_by=measure_by)

        v.trials += 1
        if res.unsafe_rate > alpha:
            v.violations += 1
        if not cal.feasible:
            continue

        v.feasible_trials += 1
        if res.unsafe_rate > alpha:
            v.violations_when_feasible += 1
        if res.worst_group_rate > alpha:
            v.group_violations += 1
        v.coverage_sum += res.coverage
        v.questions_sum += res.questions_per_case
        v.worst_sum += res.worst_group_rate
        v.concentration_sum += res.max_concentration

        # Per-band counts, so safety and coverage can be read together for
        # each band rather than pooled. Accumulated only on feasible trials,
        # matching every other figure in this object.
        for band, g in res.by_group.items():
            t = v.tally(band)
            for k in ("deployed", "unsafe", "resolved", "abstained",
                      "decidable", "questions"):
                t[k] += g[k]

    return v


def reachable_alpha(n_per_group: int, delta: float = 0.05) -> float:
    """
    Tightest tolerance `n_per_group` cases can certify, at zero failures.

    The inverse of `minimum_calibration_size`, kept because it is the form
    that answers "I have this much data, what can I promise?" — which is the
    question an operator with a fixed dataset actually has.
    """
    if n_per_group <= 0:
        return 1.0
    return clopper_pearson_upper(0, n_per_group, delta)


def trial_rate_interval(failures: int, trials: int,
                        level: float = 0.95) -> tuple[float, float]:
    """
    An exact interval for a rate measured over trials, and what it covers.

    `group_violation_rate_when_feasible` is `failures / trials`, and it was
    quoted bare in three documents until round O made it load-bearing. Two
    of those quotes needed an interval badly:

    - **2.6% on 196 trials against 2.5% on 200** read as conditioning
      narrowly losing to feature removal. The intervals are [0.8%, 5.9%] and
      [0.8%, 5.7%] — indistinguishable, which is the honest comparison.
    - **0.0% on 3 trials** read as a perfect result. Its upper bound is
      **70.8%**. Three feasible trials support almost no conclusion, and
      that is exactly the shape of the C3 miss, where an underpowered
      experiment reported no hidden subgroup and there was one.

    What this interval covers, precisely
    ------------------------------------
    Each trial is an independent draw of a calibration/deployment split from
    a **fixed** case pool, so conditional on that pool the trials are i.i.d.
    and a Clopper-Pearson interval is exact for the rate over splits. It
    quantifies Monte Carlo error, which is why re-running at another seed
    would be a redundant check rather than an additional one.

    What it does **not** cover is the pool. The 672 cases are themselves one
    sample, and the uncertainty from that is the uncertainty
    `conditional.bootstrap_band_rate` addresses for the across-trial band
    rates by resampling cases. No equivalent is computed for the per-trial
    rates here, and the gap is stated rather than papered over: these
    intervals are narrower than the uncertainty an operator actually faces.
    """
    if trials <= 0:
        return (0.0, 1.0)
    tail = (1.0 - level) / 2.0
    lo = 1.0 - clopper_pearson_upper(trials - failures, trials, tail)
    hi = clopper_pearson_upper(failures, trials, tail)
    return (lo, hi)


assert BANDS, "grouping schemes depend on conditional.BANDS being populated"
