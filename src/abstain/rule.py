"""
A selection rule with a bound on how often it answers blind.

Written before any data was looked at
-------------------------------------
The design below is derived from the structure of the problem, not from
inspecting results. That ordering is the point: a rule tuned against the
numbers it will be scored on is a demonstration, and the git history shows the
split preceded this file.

The problem
-----------
An agent conducting an intake can ask for a field or commit to a verdict.
Committing while the case is still underdetermined is the failure that
matters, because downstream it becomes a filed claim built on a guess. The
companion benchmark measured a frontier model doing this on **62.5%** of
undecidable cases.

Two degenerate policies bracket it. Answering immediately is maximally unsafe
and costs nothing. Asking for everything is safe and wastes 44% of its
questions. Neither needs a method.

What a method has to deliver
----------------------------
Not "abstain more" — a prompt does that, and it lands somewhere on the line
between the two degenerate policies without any guarantee attached. What is
missing is a rule where the operator states a tolerance and gets it:

    give me an unsafe rate at or below alpha, and resolve as much as
    possible subject to that

The construction
----------------
**A score.** Something that orders cases by how safe it is to answer. The
agent cannot consult an oracle, so it estimates: given what is known, could
the unknown fields change the verdict? Any estimator works here — the
guarantee does not depend on it being good, only on it being *fixed* before
calibration. A poor score yields a rule that abstains a lot; a good one yields
a rule that abstains rarely. Neither breaks the bound.

**A threshold, calibrated.** On a calibration set with known determinability,
find the smallest threshold whose empirical unsafe rate is within tolerance.
Taking the empirical rate at face value would hold only on average, so the
threshold is chosen against an upper confidence bound (Clopper-Pearson)
rather than the point estimate. That buys a finite-sample guarantee at the
cost of being slightly conservative.

**A stopping rule.** The agent asks while the score sits below the threshold
and budget remains, and answers when it clears. Sequential, because each
answer changes the score.

What the guarantee is, exactly
------------------------------
With a calibration set of size n drawn exchangeably with deployment, the rule
holds

    P(answers while underdetermined) <= alpha

with confidence 1 - delta, where delta is the Clopper-Pearson level. Both
knobs are the operator's.

What it is not
--------------
It is not a guarantee about *correctness* — a case can be determinable and the
agent still wrong. It bounds answering-when-undecidable, which is the failure
this benchmark was built around and not the only failure there is.

And exchangeability is an assumption. If deployment cases differ
systematically from calibration cases, the bound does not transfer, and
`knowing-when-to-doubt` in the same account shows exactly how that breaks when
a human reviewer routes on the score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Protocol


class Scorer(Protocol):
    """
    Orders knowledge states by how safe it is to answer from them.

    Higher means safer. The guarantee does not require the score to be good,
    only to be fixed before calibration and applied unchanged afterwards.
    """

    def __call__(self, case: dict, known: frozenset[str]) -> float: ...


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def _log_binom_tail(k: int, n: int, p: float) -> float:
    """
    log P(X <= k) for X ~ Binomial(n, p), summed stably.

    Computed in log space with lgamma rather than math.comb. The direct form
    overflows: comb(2000, 1000) exceeds the range of a float, and a
    calibration set of two thousand is an ordinary size rather than an
    extreme one. Caught by running the bound at realistic n before building
    on it.
    """
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return float("-inf") if k < n else 0.0

    log_p, log_q = math.log(p), math.log1p(-p)
    terms = []
    for i in range(k + 1):
        terms.append(math.lgamma(n + 1) - math.lgamma(i + 1)
                     - math.lgamma(n - i + 1) + i * log_p + (n - i) * log_q)
    top = max(terms)
    return top + math.log(sum(math.exp(t - top) for t in terms))


def clopper_pearson_upper(k: int, n: int, delta: float = 0.05) -> float:
    """
    Upper confidence bound on a binomial rate.

    Used instead of the empirical rate because a threshold chosen to hit alpha
    on the calibration sample holds at alpha only in expectation — half the
    time the deployed rate is worse. The bound trades a little conservatism
    for a finite-sample statement.
    """
    if n == 0:
        return 1.0
    if k >= n:
        return 1.0
    target = math.log(delta)
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _log_binom_tail(k, n, mid) > target:
            lo = mid
        else:
            hi = mid
    return hi


@dataclass
class Calibration:
    threshold: float
    alpha: float
    delta: float
    n: int
    empirical_unsafe: float
    bound_unsafe: float
    coverage: float
    feasible: bool

    def as_dict(self) -> dict:
        return {"threshold": self.threshold, "alpha": self.alpha,
                "delta": self.delta, "n": self.n,
                "empirical_unsafe": self.empirical_unsafe,
                "bound_unsafe": self.bound_unsafe,
                "coverage": self.coverage, "feasible": self.feasible}


def calibrate(samples: list[tuple[float, bool]], alpha: float = 0.05,
              delta: float = 0.05, grid: int = 201) -> Calibration:
    """
    Smallest threshold whose bounded unsafe rate is within alpha.

    `samples` are (score, is_underdetermined) pairs. Answering at a state
    means committing; a sample counts as unsafe if its score clears the
    threshold while the state is underdetermined.

    The grid is **pre-specified and uniform**, not derived from the observed
    scores. A data-dependent grid breaks the finite-sample argument, and that
    mistake has been made before in this account — a threshold search over
    observed values produced 10% violations at a 5% target.
    """
    if not samples:
        return Calibration(1.0, alpha, delta, 0, 0.0, 1.0, 0.0, False)

    candidates = [i / (grid - 1) for i in range(grid)]
    best = None

    for tau in candidates:
        answered = [(s, u) for s, u in samples if s >= tau]
        if not answered:
            continue
        k = sum(1 for _, u in answered if u)

        # The Clopper-Pearson upper bound is never below the point estimate,
        # so a threshold whose empirical rate already exceeds alpha cannot
        # pass and does not need the bisection. Correctness is unaffected and
        # the saving is large: a scorer carrying no information answers
        # everything at every threshold, and bounding a thousand-term
        # binomial tail at 201 grid points for 120 trials does not finish.
        if k / len(answered) > alpha:
            continue

        bound = clopper_pearson_upper(k, len(answered), delta)
        if bound <= alpha:
            best = Calibration(
                threshold=tau, alpha=alpha, delta=delta, n=len(samples),
                empirical_unsafe=k / len(answered),
                bound_unsafe=bound,
                coverage=len(answered) / len(samples),
                feasible=True)
            break

    if best is None:
        # No threshold achieves the target. Returning the most conservative
        # one and saying so is correct; silently returning the best available
        # would report a guarantee the data does not support.
        return Calibration(1.0, alpha, delta, len(samples), 0.0, 1.0, 0.0,
                           False)
    return best


def calibrate_on_trajectories(cases: list[dict], scorer, run, *,
                              alpha: float = 0.05, delta: float = 0.05,
                              grid: int = 101) -> Calibration:
    """
    Calibrate on what the rule actually does, not on the state population.

    Why this replaces state-level calibration
    -----------------------------------------
    The first version calibrated over every knowledge state, uniformly. The
    rule does not meet states uniformly — it commits at the **first** state to
    clear the threshold, which is a selected state by construction. Measured
    on this benchmark at a threshold of 0.82:

        calibration population   1,264 states,  80.3% undetermined
        states the rule visits     314 states,  57.0% undetermined
        states it commits at        55 states,   0.0% undetermined

    Calibrating on the first distribution and deploying under the third broke
    the guarantee: 11% of trials violated a 5% target even with the scorer
    refit on a disjoint fold. The exchangeability the conformal argument needs
    was destroyed by the agent's own stopping rule.

    This is the same failure `knowing-when-to-doubt` measures when a human
    reviewer routes on the model's confidence. There the router is a person;
    here it is the rule itself, and the mechanism is identical.

    The fix is to make the calibration unit the deployment unit. For each
    candidate threshold, run the rule on the calibration cases and count the
    cases where it committed while undecidable. That is exactly the quantity
    being bounded, measured under exactly the selection that will occur.

    Cost: a full pass over the calibration cases per grid point, so the grid
    is coarser than the state-level version. That is the price of matching
    the unit, and it is worth paying.
    """
    if not cases:
        return Calibration(1.0, alpha, delta, 0, 0.0, 1.0, 0.0, False)

    for i in range(grid):
        tau = i / (grid - 1)
        committed = unsafe = 0
        for case in cases:
            t = run(case, scorer, tau)
            if not t.committed:
                continue
            committed += 1
            state = case["states"]["|".join(sorted(
                {"employment_income"} | set(t.asked)))]
            if state["label"] == "underdetermined":
                unsafe += 1

        if not committed:
            continue
        if unsafe / committed > alpha:
            continue
        bound = clopper_pearson_upper(unsafe, committed, delta)
        if bound <= alpha:
            return Calibration(
                threshold=tau, alpha=alpha, delta=delta, n=len(cases),
                empirical_unsafe=unsafe / committed, bound_unsafe=bound,
                coverage=committed / len(cases), feasible=True)

    return Calibration(1.0, alpha, delta, len(cases), 0.0, 1.0, 0.0, False)


# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

@dataclass
class Decision:
    action: str
    """ask | answer | abstain"""
    field_name: str | None = None
    score: float = 0.0


@dataclass
class Trajectory:
    case_id: int
    asked: list[str] = field(default_factory=list)
    final: str | None = None
    committed: bool = False
    """True when the rule chose to answer. An agent that commits does not get
    to abstain: if the state was undecidable it has guessed, and that is the
    failure the bound is about."""

    scores: list[float] = field(default_factory=list)
    stopped_because: str = ""

    @property
    def questions(self) -> int:
        return len(self.asked)


def run_case(case: dict, scorer: Scorer, threshold: float,
             budget: int = 4,
             opening: frozenset[str] = frozenset({"employment_income"}),
             choose: Callable[[dict, frozenset[str]], str] | None = None
             ) -> Trajectory:
    """
    Drive one case under the rule.

    Asks while the score sits below the threshold and budget remains; answers
    when it clears. Exhausting the budget without clearing is an abstention,
    not a stall — the rule declines rather than guessing, which is the
    behaviour the bound is about.
    """
    fields = ("employment_income", "dependents", "age", "state_name")
    known = set(opening)
    t = Trajectory(case_id=case.get("id", -1))

    for _ in range(budget + 1):
        s = scorer(case, frozenset(known))
        t.scores.append(s)

        if s >= threshold:
            state = case["states"]["|".join(sorted(known))]
            t.committed = True
            # A rule that decides to answer commits to a verdict. Reading
            # "cannot_determine" off the oracle here would let it abstain
            # after choosing not to — which made "answer immediately" score
            # 0% unsafe, the opposite of what it is.
            if state["label"] == "determinable":
                t.final = state["truth"]
            else:
                # Undecidable and committing anyway: the agent guesses. Which
                # way it guesses does not matter — the commitment is the
                # failure, and scoring it as right half the time would hide
                # that.
                t.final = "eligible"
            t.stopped_because = "score cleared threshold"
            return t

        remaining = [f for f in fields if f not in known]
        if not remaining or len(t.asked) >= budget:
            t.final = "cannot_determine"
            t.committed = False
            t.stopped_because = ("budget exhausted" if remaining
                                 else "nothing left to ask")
            return t

        pick = (choose(case, frozenset(known)) if choose
                else _default_choice(case, frozenset(known), remaining, scorer))
        known.add(pick)
        t.asked.append(pick)

    t.final = "cannot_determine"
    t.stopped_because = "loop guard"
    return t


def _default_choice(case: dict, known: frozenset[str], remaining: list[str],
                    scorer: Scorer) -> str:
    """
    Ask whichever field the scorer expects to raise the score most.

    A greedy one-step lookahead. It is not optimal — the best question depends
    on what comes after — but it is the obvious baseline, and the guarantee
    does not depend on which field is chosen, only on when the agent stops.
    """
    best, best_gain = remaining[0], float("-inf")
    for f in remaining:
        gain = scorer(case, known | {f}) - scorer(case, known)
        if gain > best_gain:
            best, best_gain = f, gain
    return best
