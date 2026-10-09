"""
Estimating, from what the agent can see, whether the case can be decided.

What the scorer is for
----------------------
`rule.py` turns a score into a bounded decision. The bound holds for any fixed
score, so this module is not where the guarantee lives — it is where the
*coverage* lives. A score that orders cases well lets the threshold sit low
and resolve many; a score that orders them badly forces the threshold up and
the rule abstains on nearly everything. Both hold the bound.

So the scorer is judged on one thing: does it rank states by how safe they are
to answer from? Not on calibration, not on accuracy, and not on being
interpretable.

What the agent is allowed to use
--------------------------------
Only what it knows. That is the values of the fields it has been told and the
identity of the fields it has not. It may not consult the oracle, and nothing
derived from the oracle's verdict on the *current* state may enter the score —
that would be reading the answer off the thing being predicted.

The estimator may of course be *fit* on past cases where the verdicts are
known. That is ordinary supervised learning and is what the dev half is for.

Three scorers, deliberately
---------------------------
    constant       ignores everything. Establishes that the bound holds for a
                   useless score, which is the claim the theory makes.
    handcrafted    a few rules from the structure of the problem: distance
                   from the eligibility threshold, how many fields are
                   missing, whether the missing ones are the ones that matter.
    fitted         logistic regression on the same features, fit on dev.

The comparison is the evidence. If the fitted scorer beats the handcrafted one
only slightly, the handcrafted one is the better artifact — it has no training
step and nothing to leak. If it beats it substantially, the structure is
richer than the hand rules capture.

On leakage
----------
The fitted scorer is trained on one fold of dev and calibrated on another,
because a threshold calibrated on the data the score was fit to is optimistic:
the score has already seen those labels. The holdout is touched by neither.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

FIELDS = ("employment_income", "dependents", "age", "state_name")

# The SNAP gross-income limit scales with household size. An agent does not
# know the exact schedule, but distance from a rough boundary is the dominant
# structural signal and is what a competent caseworker would use.
ROUGH_LIMIT_BASE = 16_000
ROUGH_LIMIT_PER_DEPENDENT = 8_000


def features(case: dict, known: frozenset[str]) -> dict[str, float]:
    """
    What the agent can see, as numbers.

    Every feature is a function of the known field values and the identity of
    the unknown fields. Nothing here reads the oracle.
    """
    hh = case["household"]
    f: dict[str, float] = {}

    f["n_unknown"] = float(len(FIELDS) - len(known))
    for name in FIELDS:
        f[f"knows_{name}"] = 1.0 if name in known else 0.0

    income = hh["employment_income"] if "employment_income" in known else None
    deps = hh["dependents"] if "dependents" in known else None

    if income is None:
        # Income unknown is the worst case: it drives the verdict entirely.
        f["log_distance"] = 0.0
        f["income_known"] = 0.0
    else:
        f["income_known"] = 1.0
        # With dependents unknown, the limit could be anywhere in its range,
        # so distance is measured to the nearest edge of that range — the
        # agent's genuine uncertainty, not an average over it.
        if deps is None:
            lo = ROUGH_LIMIT_BASE
            hi = ROUGH_LIMIT_BASE + 3 * ROUGH_LIMIT_PER_DEPENDENT
            dist = 0.0 if lo <= income <= hi else min(abs(income - lo),
                                                      abs(income - hi))
        else:
            limit = ROUGH_LIMIT_BASE + deps * ROUGH_LIMIT_PER_DEPENDENT
            dist = abs(income - limit)
        # Log scale: the difference between 1k and 5k from the boundary
        # matters; between 40k and 44k it does not.
        f["log_distance"] = math.log1p(dist) / math.log1p(60_000)

    return f


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------

def constant_scorer(case: dict, known: frozenset[str]) -> float:
    """
    Ignores everything.

    Here to demonstrate the theory's claim: the bound holds for any fixed
    score, including a useless one. The rule built on it should abstain on
    nearly everything and violate nothing.
    """
    return 0.5


def handcrafted_scorer(case: dict, known: frozenset[str]) -> float:
    """
    A few rules taken from the structure, with no fitting.

    Confidence that the case is decidable rises with distance from the
    eligibility boundary and falls with the number of unknown fields that
    could move the verdict. Age and state move it rarely; income and
    dependents move it almost always.
    """
    f = features(case, known)

    # Income unknown means the verdict is open: sweeping it across its range
    # flips eligibility on essentially every household. Score zero.
    #
    # An arbitrary floor of 0.05 was here first, and a test caught that it
    # created an inversion — a case with income known to sit inside the
    # ambiguous band scored 0.0, below a case where income was unknown
    # entirely. Both are undecidable; neither should outrank the other.
    if not f["income_known"]:
        return 0.0

    score = f["log_distance"]

    # Unknown fields discount the score by how much they can move the answer.
    if not f["knows_dependents"]:
        score *= 0.45
    if not f["knows_state_name"]:
        score *= 0.85
    if not f["knows_age"]:
        score *= 0.95

    return max(0.0, min(1.0, score))


@dataclass
class FittedScorer:
    """
    Logistic regression on the same features, fit by gradient descent.

    Written out rather than imported so the repository has no dependency for
    one model with five parameters, and so the fitting is visible: the
    training set, the objective and the stopping rule are all in one place
    where a reviewer can see what the score was allowed to learn from.
    """

    weights: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0
    trained_on: int = 0

    excluded: tuple[str, ...] = ()
    """
    Features withheld from fitting, and why that is an experiment.

    The subgroup finding was first measured with a hand-built scorer whose
    only real feature is distance from the eligibility boundary, and the
    mechanism diagnosis blames that feature. Learning the weights over the
    same features — which is what this class normally does — rules out the
    hand-built *functional form* and leaves the *feature basis* untested.

    Fitting with `log_distance` and `income_known` excluded leaves only which
    fields the agent knows. Such a scorer cannot represent distance from the
    boundary at all, so if the concentration came from that feature it must
    disappear. It is a much weaker scorer, and that is the point: the question
    is not whether it performs well but whether one threshold over *any* score
    spends its budget unevenly when the groups differ.
    """

    def __call__(self, case: dict, known: frozenset[str]) -> float:
        f = features(case, known)
        z = self.bias + sum(self.weights.get(k, 0.0) * v for k, v in f.items()
                            if k not in self.excluded)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))

    def fit(self, samples: list[tuple[dict, frozenset[str], bool]], *,
            epochs: int = 400, lr: float = 0.5, l2: float = 1e-3,
            exclude: tuple[str, ...] = ()) -> "FittedScorer":
        """
        `samples` are (case, known, is_determinable). Label is what the
        oracle said about that state, which is legitimate supervision on
        past cases and would be unavailable at decision time.

        `exclude` names features to withhold. They are dropped from fitting
        **and** recorded on the instance so `__call__` drops them too — a
        feature excluded during training and then read at inference would be
        multiplied by a zero weight and look excluded while quietly changing
        the arithmetic if the weight ever drifted off zero.
        """
        self.excluded = tuple(exclude)
        keys = [k for k in sorted(features(samples[0][0], samples[0][1]))
                if k not in self.excluded]
        self.weights = {k: 0.0 for k in keys}
        self.bias = 0.0
        n = len(samples)
        self.trained_on = n

        rows = [(features(c, k), 1.0 if lab else 0.0) for c, k, lab in samples]

        for _ in range(epochs):
            gw = {k: 0.0 for k in keys}
            gb = 0.0
            for f, y in rows:
                z = self.bias + sum(self.weights[k] * f.get(k, 0.0) for k in keys)
                p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
                err = p - y
                gb += err
                for k in keys:
                    gw[k] += err * f.get(k, 0.0)
            self.bias -= lr * gb / n
            for k in keys:
                self.weights[k] -= lr * (gw[k] / n + l2 * self.weights[k])

        return self

    def as_dict(self) -> dict:
        return {"bias": self.bias, "weights": self.weights,
                "trained_on": self.trained_on,
                "excluded": list(self.excluded)}


# ---------------------------------------------------------------------------
# Quality of the ordering
# ---------------------------------------------------------------------------

def auc(samples: list[tuple[float, bool]]) -> float:
    """
    Probability a randomly chosen determinable state scores above a randomly
    chosen underdetermined one.

    The right measure here because the rule only ever uses the score's
    *order*. Calibration of the score itself is irrelevant — the threshold
    handles that — so reporting log-loss or accuracy would be measuring
    something the method does not use.
    """
    pos = [s for s, d in samples if d]
    neg = [s for s, d in samples if not d]
    if not pos or not neg:
        return 0.5
    wins = ties = 0
    for p in pos:
        for q in neg:
            if p > q:
                wins += 1
            elif p == q:
                ties += 1
    return (wins + 0.5 * ties) / (len(pos) * len(neg))


# ---------------------------------------------------------------------------
# The scorer the mechanism diagnosis implies
# ---------------------------------------------------------------------------

AWARD_RISK_WEIGHT = 0.8
"""
Fixed in `docs/preregistration-5.md` before the first run, and not adjusted.

Chosen so the penalty is nearly total at maximal distance from the boundary,
which is where the measurement says the scorer is most wrong. One value, no
sweep: a constant tuned after seeing the result it produces is not a fix, it
is a fit.
"""


def award_aware_scorer(case: dict, known: frozenset[str]) -> float:
    """
    `handcrafted_scorer` plus the term the failure analysis asks for.

    What it is repairing
    --------------------
    The handcrafted scorer estimates whether **eligibility** is settled.
    Determinability on this benchmark requires the **award** to be settled
    too — sweeping the unknown fields must not move it by more than the
    materiality threshold. Far below the income limit eligibility is obvious
    and the award swings hardest with household size, so the scorer is
    confident, correct about its own question, and wrong about the one it is
    scored on. Measured: **72%** of its commitments in `well-below` are
    award-only against 0% in `above`.

    Why the existing discount is not already this
    ---------------------------------------------
    `handcrafted_scorer` multiplies by 0.45 when `dependents` is unknown,
    uniformly. Right direction, wrong shape. Near the income boundary an
    unknown household size threatens **eligibility**, and `log_distance`
    already collapses the score there. Far below it threatens the **award**,
    and nothing in the score notices — so the one place the flat discount
    leaves the score high is the one place it should not.

    So the award term scales **with** distance, which is the inverse of how
    the rest of the score behaves:

        award_risk = distance   if dependents unknown else 0
        score      = handcrafted × (1 − award_risk × AWARD_RISK_WEIGHT)

    Nothing here consults the oracle. The agent knows the household size it
    has been told and the one it has not, which is all the term needs — it
    does not estimate the award, only whether the award is pinned down.
    """
    base = handcrafted_scorer(case, known)
    if base <= 0.0 or "dependents" in known:
        return base

    f = features(case, known)
    award_risk = f["log_distance"] if f["income_known"] else 1.0
    return max(0.0, base * (1.0 - award_risk * AWARD_RISK_WEIGHT))
