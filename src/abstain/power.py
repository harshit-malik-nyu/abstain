"""
How much data does a claim need before it is a claim?

Why this module exists
----------------------
Round three set out to test whether group-conditional calibration fixes the
subgroup concentration experiment C found. It could not. Both sides of the
experiment were too small, and the numbers it produced were noise:

**Calibration side.** Dev's 60% fold is 47 cases over four income bands, about
11 each. A Clopper–Pearson bound with zero observed failures in 11 trials is
still 23.8%, so no tolerance at or below 20% is reachable in principle — and
all three pre-registered tolerances are. The grouped rule was infeasible in
100% of trials at every one of them, which is arithmetic rather than a result.

**Evaluation side,** and this is the one that is easy to miss. The deployment
fold is about 32 cases, so each band holds roughly 8. A rate measured on 8
cases moves in steps of 12.5 points: 0/8 and 1/8 are 0% and 12.5%, and nothing
lies between. Asking whether a band's rate exceeds a 10% tolerance on 8 cases
is asking a question the measurement cannot resolve.

So the honest conclusion for round three is not "the fix does not work". It is
**"this experiment cannot tell"** — and the useful output is the number of
cases at which it could.

That number is computable in advance, which is the point. Both sides below are
closed forms or exact binomial computations, not simulations, so they can be
read off before collecting data rather than discovered after.

What this is not
----------------
Not a substitute for having run the experiment. A power calculation says what
a design could detect; it says nothing about what is true. It is here so that
an underpowered result is reported as underpowered with the shortfall
quantified, rather than reported as a negative finding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .rule import clopper_pearson_upper


def calibration_cases_needed(alpha: float, delta: float = 0.05) -> int:
    """
    Fewest calibration cases, per group, that can certify `alpha` at all.

        n >= ln(delta) / ln(1 - alpha)

    From the Clopper–Pearson bound at zero observed failures, 1 − δ^(1/n) ≤ α.
    A hard floor: independent of the scorer, the benchmark and the method's
    quality. Duplicated from `group.minimum_calibration_size` and pinned equal
    to it by test, so the power analysis and the calibrator cannot disagree
    about the floor they share.
    """
    if not 0.0 < alpha < 1.0 or not 0.0 < delta < 1.0:
        raise ValueError("alpha and delta must lie in (0, 1)")
    return math.ceil(math.log(delta) / math.log(1.0 - alpha))


def resolution(n: int) -> float:
    """
    The smallest non-zero rate measurable on `n` cases: 1/n.

    Trivial and worth naming. A per-band rate on 8 deployed cases has a
    resolution of 12.5 points, so a 10% tolerance sits *between* two
    measurable values and "did this band exceed 10%" has no answer at that
    sample size. Round three asked exactly that question.
    """
    return 1.0 / n if n > 0 else 1.0


def deployment_cases_needed(alpha: float, effect: float,
                            confidence: float = 0.95) -> int:
    """
    Cases per group to distinguish a true rate of `effect` from `alpha`.

    Exact rather than normal-approximate. For each n, the one-sided
    Clopper–Pearson upper bound at the observed count nearest `effect` is
    compared against `alpha`: n is sufficient when a group whose true rate is
    `effect` yields a bound that excludes `alpha`.

    The normal approximation is wrong in exactly the regime that matters here
    — small n, small p, a bound near the boundary — and a power calculation
    that uses it would understate the requirement for the quantity this
    project is about. The same reason the method uses an exact bound rather
    than a Wald interval.

    `effect` below `alpha` asks for the sample size needed to *confirm* a band
    is within budget; above it, to *detect* that a band is over. Both are
    useful and the asymmetry is real, so the direction is the caller's.
    """
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie in (0, 1)")
    if effect <= 0.0 or effect >= 1.0:
        raise ValueError("effect must lie in (0, 1)")
    delta = 1.0 - confidence

    for n in range(1, 20_001):
        k = round(effect * n)
        if effect < alpha:
            # Confirming within budget: the upper bound has to fall under
            # alpha.
            if clopper_pearson_upper(k, n, delta) <= alpha:
                return n
        else:
            # Detecting over budget: the *lower* bound has to clear alpha,
            # which by symmetry is the upper bound on the complement.
            if 1.0 - clopper_pearson_upper(n - k, n, delta) >= alpha:
                return n
    return 20_001


@dataclass(frozen=True)
class Requirement:
    """What one subgroup experiment needs, on both sides."""

    alpha: float
    delta: float
    groups: int
    smallest_group_share: float
    calibration_per_group: int
    deployment_per_group: int
    calibration_share: float = 0.6

    @property
    def calibration_total(self) -> int:
        """Driven by the *smallest* group, since feasibility is conjunctive."""
        return math.ceil(self.calibration_per_group / self.smallest_group_share)

    @property
    def deployment_total(self) -> int:
        return math.ceil(self.deployment_per_group / self.smallest_group_share)

    @property
    def cases_needed(self) -> int:
        """
        Total benchmark size at the **fixed** calibration share.

        The two folds come out of one pool at a set share, so the pool has to
        satisfy both constraints at that share: share·N ≥ calibration_total
        and (1 − share)·N ≥ deployment_total. The maximum of the two ratios,
        not the sum — the folds are drawn from the same cases.

        This can exceed `calibration_total + deployment_total`, and at the
        project's default share it does. That is not an error; it is the cost
        of a share that does not match what the experiment needs, and
        `cases_needed_at_best_share` below says what the mismatch costs.
        """
        from_cal = self.calibration_total / self.calibration_share
        from_dep = self.deployment_total / (1.0 - self.calibration_share)
        return math.ceil(max(from_cal, from_dep))

    @property
    def best_calibration_share(self) -> float:
        """
        The share at which neither constraint is slack.

        Both bind when share·N = C and (1 − share)·N = D, which gives
        N = C + D at share = C / (C + D). So the smallest possible pool is
        exactly the sum, and any other share wastes cases on the fold that
        is not binding.

        Worth having because the default 0.6 is wrong for this experiment and
        was not obviously wrong. Group conditioning inflates the
        **deployment** requirement much harder than the calibration one — a
        per-band rate has to be resolvable, which needs cases in every band at
        deployment — so a share tuned for pooled validation starves the side
        that now matters. Found by a failing test rather than by inspection:
        an assertion that `cases_needed` would come in under the sum, which
        at alpha = 0.15 it does not (500 against 295).
        """
        total = self.calibration_total + self.deployment_total
        return self.calibration_total / total if total else 0.5

    @property
    def cases_needed_at_best_share(self) -> int:
        return self.calibration_total + self.deployment_total

    @property
    def share_penalty(self) -> float:
        """How many times larger the fixed-share design has to be."""
        best = self.cases_needed_at_best_share
        return self.cases_needed / best if best else 1.0

    def as_dict(self) -> dict:
        return {"alpha": self.alpha, "delta": self.delta,
                "groups": self.groups,
                "smallest_group_share": self.smallest_group_share,
                "calibration_per_group": self.calibration_per_group,
                "deployment_per_group": self.deployment_per_group,
                "calibration_total": self.calibration_total,
                "deployment_total": self.deployment_total,
                "calibration_share": self.calibration_share,
                "cases_needed": self.cases_needed,
                "best_calibration_share": self.best_calibration_share,
                "cases_needed_at_best_share":
                    self.cases_needed_at_best_share,
                "share_penalty": self.share_penalty}


def requirement(alpha: float, *, delta: float = 0.05, groups: int = 4,
                smallest_group_share: float = 0.20,
                effect: float = 0.05,
                calibration_share: float = 0.6) -> Requirement:
    """
    The design round three should have had.

    `smallest_group_share` is what binds, not the average share. Feasibility
    under group conditioning is conjunctive — one group without a threshold
    means the whole calibration failed — so the group that gets the fewest
    cases sets the requirement for all of them. Dev's smallest band is 20.3%
    of cases, hence the default.

    `effect` is the rate a group would have to be at for the experiment to
    resolve it against `alpha`. The default of 0.05 asks: how many cases to
    confirm a group is genuinely at 5% rather than at the 10% tolerance?
    """
    return Requirement(
        alpha=alpha, delta=delta, groups=groups,
        smallest_group_share=smallest_group_share,
        calibration_per_group=calibration_cases_needed(alpha, delta),
        deployment_per_group=deployment_cases_needed(
            alpha, effect, confidence=1.0 - delta),
        calibration_share=calibration_share)


def shortfall(have: int, alpha: float, **kw) -> dict:
    """
    What a benchmark of `have` cases can and cannot support at `alpha`.

    Written to be callable on the benchmark actually in hand, so that
    "underpowered" is a ratio rather than an adjective.
    """
    r = requirement(alpha, **kw)
    return {"have": have, "needed": r.cases_needed,
            "factor_short": round(r.cases_needed / have, 2) if have else None,
            "adequate": have >= r.cases_needed,
            "requirement": r.as_dict()}
