"""
What does the assumption cost when it is false?

Why this module is the one the repository was missing
-----------------------------------------------------
Every guarantee here rests on exchangeability: the deployed cases are drawn
like the calibration cases. `rule.py` states it, `validate.py` says in its own
docstring that it cannot test it, `docs/theory.md` lists it as an assumption,
and the README points at a sibling project for what happens when it breaks.

So the project's central caveat was asserted and never priced. A reader had no
way to tell whether exchangeability is a technicality or the whole thing.

It is cheap to price, because the apparatus already exists. The income bands
partition the benchmark and round four established that they behave very
differently — `well-below` runs at 45.7% unsafe against a pooled 11.1% at
α = 0.20. So **re-weighting the bands between calibration and deployment is a
covariate shift with a known mechanism and a realistic story**: a benefits
agency whose applicant mix moves toward the lowest-income band.

The construction
----------------
Calibrate on the natural mix. Deploy on a mix where one band's share is forced
to `target_share`, sweeping it upward. Calibration is held unshifted in every
condition on purpose — the operator does not know the shift is coming, which
is what makes it a shift rather than a different problem.

What this is and is not
-----------------------
It is a measurement of what the **unweighted** method costs when its
assumption is false. Conformal prediction under distribution shift has a
literature — weighted conformal methods among others — and none of it is
implemented here.

It is also not a test of robustness in general. Group-conditional calibration
should survive *this* shift, because re-weighting groups that were calibrated
separately changes which thresholds get used and not what any threshold is.
That is a narrow invariance and it is worth being precise about: a shift
*within* a band, a band calibration never saw, or a change in the relationship
between the score and determinability all break group conditioning exactly as
they break the pooled rule.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .conditional import BANDS, hardness
from .group import calibrate_by_group, evaluate_by_group
from .validate import trial_split


def reweight(cases: list[dict], band: str, target_share: float,
             rng: random.Random, size: int | None = None) -> list[dict]:
    """
    Resample `cases` so that `band` makes up `target_share` of the result.

    Sampling **with replacement** within each stratum, because forcing a band
    to 80% of a fold when it is 14% of the pool cannot be done by subsetting —
    there are not enough of those cases. The alternative, discarding cases
    from the other bands until the ratio comes out, shrinks the fold as the
    shift grows and confounds the shift with sample size.

    So the fold keeps its size and the composition changes, which is what a
    covariate shift is. The cost is that at a high target share the same
    `well-below` case appears many times, and the deployed rate is then an
    average over fewer distinct cases than the count suggests. That is a real
    limitation of this harness and is reported alongside the result as the
    number of distinct cases behind each figure.
    """
    if not 0.0 <= target_share <= 1.0:
        raise ValueError(f"target_share must be in [0, 1], got {target_share}")

    inside = [c for c in cases if hardness(c) == band]
    outside = [c for c in cases if hardness(c) != band]
    if not inside or (target_share < 1.0 and not outside):
        return []

    n = size if size is not None else len(cases)
    n_in = round(n * target_share)
    n_out = n - n_in

    out = [rng.choice(inside) for _ in range(n_in)]
    out += [rng.choice(outside) for _ in range(n_out)]
    rng.shuffle(out)
    return out


@dataclass
class ShiftPoint:
    """One (scheme, alpha, target_share) condition."""

    scheme: str
    alpha: float
    target_share: float
    trials: int = 0
    feasible_trials: int = 0
    violations: int = 0
    unsafe_sum: float = 0.0
    coverage_sum: float = 0.0
    bound_sum: float = 0.0
    distinct_sum: int = 0
    deployed_sum: int = 0
    bands: dict[str, dict] = field(default_factory=dict)
    """
    Per-band counts, pooled over feasible trials.

    Needed for G3, which asks whether a RECALIBRATED pooled rule still
    concentrates. Recalibration restores the marginal guarantee; whether it
    evens out the budget is a different question, and the violation rate
    alone cannot answer it.
    """

    def tally(self, band: str) -> dict:
        if band not in self.bands:
            self.bands[band] = {"deployed": 0, "unsafe": 0}
        return self.bands[band]

    @property
    def worst_band_rate(self) -> float:
        seen = [b for b in self.bands.values() if b["deployed"]]
        return max((b["unsafe"] / b["deployed"] for b in seen), default=0.0)

    @property
    def max_concentration(self) -> float:
        total_d = sum(b["deployed"] for b in self.bands.values())
        total_u = sum(b["unsafe"] for b in self.bands.values())
        if not total_u or not total_d:
            return 0.0
        return max(((b["unsafe"] / total_u) / (b["deployed"] / total_d))
                   for b in self.bands.values() if b["deployed"])

    @property
    def hides_a_subgroup(self) -> bool:
        """Pooled rate inside budget while some band is outside it."""
        total_d = sum(b["deployed"] for b in self.bands.values())
        total_u = sum(b["unsafe"] for b in self.bands.values())
        if not total_d or (total_u / total_d) > self.alpha:
            return False
        return self.worst_band_rate > self.alpha

    @property
    def violation_rate(self) -> float | None:
        if not self.feasible_trials:
            return None
        return self.violations / self.feasible_trials

    def _mean(self, total: float) -> float:
        return total / self.feasible_trials if self.feasible_trials else 0.0

    @property
    def mean_reported_bound(self) -> float:
        """
        The certificate the method issued, averaged.

        Computed on calibration data, which is unshifted in every condition,
        so this should stay flat while the deployed rate climbs. That gap is
        the measurement of whether the failure is silent.
        """
        return self._mean(self.bound_sum)

    @property
    def distinct_fraction(self) -> float:
        """
        Distinct deployed cases over deployed slots.

        Falls as the shift grows, because forcing a 14% band to 80% of the
        fold means resampling it with replacement. Reported so a reader can
        discount the high-shift conditions rather than take them at face
        value.
        """
        return (self.distinct_sum / self.deployed_sum
                if self.deployed_sum else 0.0)

    def as_dict(self) -> dict:
        return {"scheme": self.scheme, "alpha": self.alpha,
                "target_share": self.target_share,
                "trials": self.trials,
                "feasible_trials": self.feasible_trials,
                "violation_rate": self.violation_rate,
                "mean_unsafe_rate": self._mean(self.unsafe_sum),
                "mean_coverage": self._mean(self.coverage_sum),
                "mean_reported_bound": self.mean_reported_bound,
                "distinct_fraction": self.distinct_fraction,
                "worst_band_rate": self.worst_band_rate,
                "max_concentration": self.max_concentration,
                "hides_a_subgroup": self.hides_a_subgroup,
                "bands": {k: dict(v) for k, v in sorted(self.bands.items())}}


@dataclass
class ShiftSweep:
    band: str
    points: list[ShiftPoint] = field(default_factory=list)
    shift_calibration: bool = False
    """Whether the operator was allowed to recalibrate on the shifted mix."""

    def for_scheme(self, scheme: str, alpha: float) -> list[ShiftPoint]:
        return [p for p in self.points
                if p.scheme == scheme and p.alpha == alpha]

    def monotone(self, scheme: str, alpha: float) -> bool:
        """Is the violation rate non-decreasing in the shift?"""
        rates = [p.violation_rate or 0.0
                 for p in sorted(self.for_scheme(scheme, alpha),
                                 key=lambda p: p.target_share)]
        return rates == sorted(rates)

    def as_dict(self) -> dict:
        return {"band": self.band,
                "shift_calibration": self.shift_calibration,
                "points": [p.as_dict() for p in self.points]}


def sweep_shift(cases: list[dict], scorer, *, band: str = "well-below",
                shares: tuple[float, ...] = (0.143, 0.25, 0.40, 0.60, 0.80,
                                             1.00),
                schemes: tuple[str, ...] = ("pooled", "by-band"),
                alphas: tuple[float, ...] = (0.20, 0.15),
                trials: int = 300, seed: int = 41,
                calibration_share: float = 0.30,
                delta: float = 0.05,
                shift_calibration: bool = False) -> ShiftSweep:
    """
    Calibrate, deploy shifted, count violations.

    Both schemes see the **same** calibration fold and the **same** reweighted
    deployment fold in every trial, drawn from `validate.trial_split` and a
    per-trial stream that depends only on the trial index. So the comparison
    between pooled and group-conditional is paired, and a difference between
    them is not a difference in which cases they happened to get.

    `shift_calibration` and the objection it answers
    ------------------------------------------------
    Left false, calibration stays at the natural mix however far deployment
    moves. That is the right model for the *onset* of a shift — the operator
    does not know it is coming — and the wrong one afterwards, which leaves
    the whole round open to a one-line rebuttal: of course the pooled rule
    fails, it was never allowed to recalibrate.

    Set true, the calibration fold is reweighted to the same share as the
    deployment fold. The operator now knows the mix and has recalibrated on
    it, and the question becomes the one a practitioner actually faces:

        is the fix "calibrate per group", or just "recalibrate often"?

    The second is easier and already standard practice, so if recalibration
    alone restores both validity and an even error budget, the recommendation
    from this repository is the weaker one and should say so.
    """
    sweep = ShiftSweep(band=band, shift_calibration=shift_calibration)

    for scheme in schemes:
        for alpha in alphas:
            for share in shares:
                pt = ShiftPoint(scheme=scheme, alpha=alpha,
                                target_share=share)
                for t in range(trials):
                    _, cal_cases, dep_cases = trial_split(
                        cases, trial=t, seed=seed,
                        calibration_share=calibration_share)
                    if not cal_cases or not dep_cases:
                        continue

                    # Keyed on the trial alone, so every scheme, alpha and
                    # share that uses trial t gets the identical reweighted
                    # fold. Folding scheme or alpha into the seed would make
                    # the arms differ by their draw as well as by the thing
                    # being varied.
                    rng = random.Random(seed * 7_919 + t)
                    shifted = reweight(dep_cases, band, share, rng)
                    if not shifted:
                        continue

                    fold = cal_cases
                    if shift_calibration:
                        # A separate stream, so the calibration fold's
                        # resampling is not the deployment fold's draw
                        # repeated -- that would make the two folds share
                        # cases in the same order and the split stop being
                        # disjoint in effect.
                        cal_rng = random.Random(seed * 104_729 + t)
                        fold = reweight(cal_cases, band, share, cal_rng)
                        if not fold:
                            continue

                    cal = calibrate_by_group(fold, scorer, scheme=scheme,
                                             alpha=alpha, delta=delta)
                    pt.trials += 1
                    if not cal.feasible:
                        continue
                    pt.feasible_trials += 1

                    res = evaluate_by_group(shifted, scorer, cal)
                    if res.unsafe_rate > alpha:
                        pt.violations += 1
                    pt.unsafe_sum += res.unsafe_rate
                    pt.coverage_sum += res.coverage
                    pt.bound_sum += max(
                        (g["bound_unsafe"] for g in cal.per_group.values()),
                        default=1.0)
                    # Counted by case id, not object identity: `reweight` draws
                    # the same dict object repeatedly, so `id()` would
                    # happen to work here and would break silently the
                    # moment a copy was introduced.
                    pt.distinct_sum += len({c["id"] for c in shifted})
                    pt.deployed_sum += len(shifted)
                    for name, g in res.by_group.items():
                        t = pt.tally(name)
                        t["deployed"] += g["deployed"]
                        t["unsafe"] += g["unsafe"]

                sweep.points.append(pt)

    return sweep


def natural_share(cases: list[dict], band: str) -> float:
    return sum(1 for c in cases if hardness(c) == band) / len(cases) \
        if cases else 0.0


def sanity_unshifted(cases: list[dict], scorer, *, alpha: float = 0.20,
                     trials: int = 50, seed: int = 41) -> dict:
    """
    The pooled rule without any shift, through the ordinary path.

    F1's control runs the shift harness at the natural share and expects it to
    look like this. If the two disagree the harness is introducing something,
    and every number in the sweep is then about the harness rather than about
    shift.
    """
    from .validate import validate
    v = validate(cases, scorer, alpha=alpha, trials=trials, seed=seed,
                 calibration_share=0.30)
    return v.as_dict()


assert set(BANDS) == {"well-below", "near-threshold", "above", "well-above"}, \
    "the shift sweep names a band literal; keep it in step with BANDS"
