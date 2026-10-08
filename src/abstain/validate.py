"""
Does the bound hold, or is it only stated?

Why this is the central experiment
----------------------------------
The method's claim is not that it performs well. It is that an operator can
name a tolerance and get it:

    P(answers while undecidable) <= alpha, with confidence 1 - delta

A single run cannot test that. One calibration set, one deployment set, one
observed rate — if the rate comes in under alpha it proves nothing, because a
procedure that violates its bound a third of the time will still look fine on
any given draw.

What tests it is repetition. Draw a calibration set, calibrate, deploy on
disjoint cases, record whether the realised unsafe rate exceeded alpha. Over
many trials the violation rate should sit at or below delta. If it sits above,
the guarantee is decorative.

What would make this experiment dishonest
-----------------------------------------
**A shared random stream.** If the same generator drives the calibration draw
and the deployment draw, the two are coupled and the arms move together. That
mistake was made in `knowing-when-to-doubt` and produced an oracle arm that
drifted with the pilot size, which looked like a finding and was a bug. Here
each trial seeds the two draws independently.

**Reusing cases across arms.** A case in both calibration and deployment makes
the deployed rate optimistic for the obvious reason. The split is disjoint and
asserted to be.

**Reporting the mean.** A bound is not an average. The quantity of interest is
the share of trials that violated, not the mean realised rate, and a procedure
can have a comfortable mean while violating often.

What it cannot test
-------------------
Exchangeability. Every trial draws calibration and deployment from the same
pool, which is exactly the assumption the guarantee needs — so this validates
the finite-sample argument and says nothing about what happens when deployment
differs from calibration. `knowing-when-to-doubt` in the same account measures
that case and finds the guarantee breaks.
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field

from .evaluate import evaluate
from .rule import calibrate, calibrate_on_trajectories, run_case
from .scorer import FIELDS


def states_of(cases: list[dict]) -> list[tuple[dict, frozenset[str], bool]]:
    """Every (case, knowledge state, is_determinable) triple."""
    out = []
    for c in cases:
        for r in range(len(FIELDS) + 1):
            for known in itertools.combinations(FIELDS, r):
                label = c["states"]["|".join(sorted(known))]["label"]
                out.append((c, frozenset(known), label == "determinable"))
    return out


@dataclass
class Trial:
    threshold: float
    feasible: bool
    realised_unsafe: float
    coverage: float
    questions: float
    violated: bool


@dataclass
class Validation:
    alpha: float
    delta: float
    trials: int = 0
    results: list[Trial] = field(default_factory=list)

    @property
    def violation_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(t.violated for t in self.results) / len(self.results)

    @property
    def infeasible_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(not t.feasible for t in self.results) / len(self.results)

    @property
    def mean_coverage(self) -> float:
        usable = [t for t in self.results if t.feasible]
        return sum(t.coverage for t in usable) / len(usable) if usable else 0.0

    @property
    def mean_questions(self) -> float:
        usable = [t for t in self.results if t.feasible]
        return sum(t.questions for t in usable) / len(usable) if usable else 0.0

    @property
    def holds(self) -> bool:
        """
        Judged against delta, which is what the Clopper-Pearson level buys.

        A little slack is allowed because the violation rate is itself
        estimated from a finite number of trials; the slack is one standard
        error of a binomial at delta, not a round number chosen to pass.
        """
        if not self.results:
            return False
        se = (self.delta * (1 - self.delta) / len(self.results)) ** 0.5
        return self.violation_rate <= self.delta + 2 * se

    def as_dict(self) -> dict:
        return {"alpha": self.alpha, "delta": self.delta,
                "trials": len(self.results),
                "violation_rate": self.violation_rate,
                "infeasible_rate": self.infeasible_rate,
                "mean_coverage": self.mean_coverage,
                "mean_questions": self.mean_questions,
                "holds": self.holds}


def validate(cases: list[dict], scorer, *, alpha: float = 0.05,
             delta: float = 0.05, trials: int = 200,
             calibration_share: float = 0.6, seed: int = 0,
             refit=None, unit: str = "trajectory") -> Validation:
    """
    Repeatedly calibrate and deploy on disjoint halves, counting violations.

    The two draws are seeded independently per trial, so the calibration set
    and the deployment set do not move together. Coupling them would make the
    arms correlated and the violation rate meaningless.

    `refit` and why it exists
    -------------------------
    Pass a callable taking the fitting cases and returning a scorer, and each
    trial trains a fresh one on a fold disjoint from both calibration and
    deployment.

    Without it, a *fitted* scorer evaluated here has already seen the
    deployment cases during training, and the guarantee does not survive it:
    measured on this benchmark, a logistic scorer fit on the whole pool
    violated a 5% target in **35.8%** of trials, while a handcrafted scorer
    with no training step violated none.

    That is not a defect of the bound. The conformal argument requires the
    score to be fixed with respect to the calibration and deployment data,
    and a score fit on them is not. The failure is worth keeping visible
    because it is silent: the threshold looks reasonable, the calibration
    reports its bound, and the deployed rate is seven times the target.
    """
    v = Validation(alpha=alpha, delta=delta)

    for t in range(trials):
        # Independent streams: one picks the calibration cases, the other is
        # reserved for anything stochastic in deployment. Sharing one stream
        # is the bug that produced a drifting oracle arm in a sibling project.
        rng_split = random.Random(seed * 10_007 + t)

        shuffled = cases[:]
        rng_split.shuffle(shuffled)

        active = scorer
        if refit is not None:
            # Three disjoint folds: fit, calibrate, deploy. The scorer never
            # sees a case it will later be calibrated or scored on.
            third = len(shuffled) // 3
            fit_cases = shuffled[:third]
            rest = shuffled[third:]
            if not fit_cases:
                continue
            active = refit(fit_cases)
        else:
            rest = shuffled

        cut = int(len(rest) * calibration_share)
        cal_cases, dep_cases = rest[:cut], rest[cut:]
        if not cal_cases or not dep_cases:
            continue

        if unit == "trajectory":
            cal = calibrate_on_trajectories(
                cal_cases, active,
                lambda c, sc, tau: run_case(c, sc, tau, budget=4),
                alpha=alpha, delta=delta)
        else:
            samples = [(active(c, k), not determinable)
                       for c, k, determinable in states_of(cal_cases)]
            cal = calibrate(samples, alpha=alpha, delta=delta)

        res = evaluate(dep_cases, active, cal.threshold, "trial")
        v.results.append(Trial(
            threshold=cal.threshold, feasible=cal.feasible,
            realised_unsafe=res.unsafe_rate, coverage=res.coverage,
            questions=res.questions_per_case,
            violated=res.unsafe_rate > alpha))

    return v


def sweep_alpha(cases: list[dict], scorer, *,
                alphas: tuple[float, ...] = (0.20, 0.10, 0.05, 0.02),
                trials: int = 120, seed: int = 0) -> list[dict]:
    """
    The guarantee across tolerances.

    A method that holds at one alpha and not another is not delivering the
    knob it advertises. The expected shape is monotone: tighter tolerance,
    higher threshold, less coverage, more questions — and the violation rate
    staying under delta throughout.
    """
    return [validate(cases, scorer, alpha=a, trials=trials,
                     seed=seed).as_dict() for a in alphas]
