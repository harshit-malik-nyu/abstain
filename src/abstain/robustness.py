"""
Does the bound survive a bad score?

The claim being tested
----------------------
`rule.py` says the guarantee "does not depend on [the score] being good, only
on it being *fixed* before calibration." That is the conformal argument's
actual content and it is a strong statement: it makes score quality a
*coverage* question and not a *safety* question. A good score lets the
threshold sit low and resolve many cases; a bad one forces it up and the rule
abstains. Neither should break the bound.

Stated, it has been. Tested, it has not — every number in this repository
comes from one hand-built scorer that happens to work. `docs/against.md`
already leads with the objection: there is no model in it. This module is the
answer that does not require one.

Why corruption rather than a language model
-------------------------------------------
The obvious experiment is to swap the handcrafted score for a frontier
model's self-reported confidence and see whether the bound holds. That is one
sample of one score function, and it would conflate two things: whether the
bound survives bad scores in general, and whether it survives *that* score.

Corruption separates them. Each transform below is a named, reproducible
pathology, and the set spans from "slightly degraded" to "actively
adversarial". If the bound holds across the whole range, the claim is
supported for any score inside it — which includes a miscalibrated language
model, because the specific ways model confidence goes wrong are in the list:

    coarse     values pile on round numbers. A model asked for confidence
               returns 0.9, 0.95, 0.99 and little else, and the fine ordering
               the rule would like is simply absent.
    sharpen    overconfidence. Everything is pushed toward 1. **Monotone**,
               so the ordering survives intact, which makes it the sharpest
               probe in the set: the rule's stopping condition is a threshold
               comparison and should be blind to it.
    noisy      the ordering itself degrades. Not a model pathology so much as
               a dial, to trace coverage against rank quality.
    constant   no information at all.
    inverted   anti-correlated. The least safe states score highest.

`inverted` is not a plausible scorer and is not meant to be. It is the worst
case the theory claims to cover, and a theory's worst case is the only part of
it worth testing.

What is held fixed
------------------
Every corruption is applied **identically in calibration and deployment**.
That is deliberate and it is the whole experiment: exchangeability is the
assumption the conformal argument needs, and these transforms do not touch
it. They vary score quality while holding the assumption, so a violation here
would be a violation of the theory rather than of its precondition.

The complementary experiment — breaking exchangeability and watching the bound
fail — is already done, twice. `calibrate_on_trajectories` documents the
agent's own stopping rule doing it, and `knowing-when-to-doubt` in the same
account measures a human reviewer doing it. Those are the assumption. This is
the theorem.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass
from typing import Callable

from .scorer import handcrafted_scorer

Scorer = Callable[[dict, frozenset], float]


# ---------------------------------------------------------------------------
# The corruptions
# ---------------------------------------------------------------------------

def identity(base: Scorer = handcrafted_scorer) -> Scorer:
    """Control. Present so the comparison has a same-shaped baseline."""
    def sc(case, known):
        return base(case, known)
    return sc


def coarse(base: Scorer = handcrafted_scorer, step: float = 0.1) -> Scorer:
    """
    Round to a grid, imitating the clumping of self-reported confidence.

    Creates large ties, which matters more than it looks: the rule commits at
    the first state whose score clears the threshold, and when many states
    share a score the threshold can no longer separate them. Coverage should
    fall in steps rather than smoothly as the tolerance tightens.
    """
    def sc(case, known):
        return round(base(case, known) / step) * step
    return sc


def sharpen(base: Scorer = handcrafted_scorer, power: float = 0.25) -> Scorer:
    """
    s -> s**power. Overconfidence: everything pushed toward 1.

    Strictly monotone on [0, 1], so the **ordering is unchanged** and AUC is
    identical to the nearest floating-point bit. That makes this the one
    corruption whose effect on coverage is a direct test of a structural
    claim: the stopping rule compares a score to a threshold and so reads
    only the order, and if coverage moves anyway, something else in the
    pipeline is reading the value.

    Something else is, and the pre-registration says so in advance:
    `_default_choice` picks the next question by the largest score
    *difference*, and differences are not monotone-invariant. Whether that is
    enough to move coverage is the measurement.
    """
    def sc(case, known):
        return base(case, known) ** power
    return sc


def noisy(base: Scorer = handcrafted_scorer, sigma: float = 0.1,
          seed: int = 0) -> Scorer:
    """
    Add Gaussian noise, clipped to [0, 1]. A dial on ordering quality.

    The noise is **deterministic in (case, known)** rather than drawn fresh on
    each call, and that is not a convenience — it is required. The rule
    evaluates the same state more than once (the greedy question-selector
    looks ahead, then the stopping rule scores the state it lands on), and a
    score that returns a different value each time is not a function. It would
    break the one thing the guarantee genuinely needs: that the score is
    fixed. The violation would then be attributable to a non-deterministic
    score rather than to a bad one, and the experiment would be measuring the
    wrong thing.

    So the seed is derived from the case id and the known-field set, which
    makes the corrupted scorer a well-defined function that happens to look
    random.

    The derivation goes through SHA-256 rather than `hash()`. Python salts
    string hashing per process, so `hash(("age", "dependents"))` returns a
    different value in every interpreter — the first version of this function
    used it, and the corrupted scorer was consequently a different function on
    every run. Verified rather than assumed: three subprocesses gave
    2289478572, 4227375128, 431682884 for the same key. An experiment whose
    scorer changes between runs cannot be replicated, and a reproducibility
    claim that has not been checked across processes has not been checked.
    """
    def sc(case, known):
        key = f"{seed}|{case.get('id', -1)}|{','.join(sorted(known))}"
        digest = hashlib.sha256(key.encode()).digest()[:8]
        rng = random.Random(int.from_bytes(digest, "big"))
        return max(0.0, min(1.0, base(case, known) + rng.gauss(0.0, sigma)))
    return sc


def constant(value: float = 0.5) -> Scorer:
    """No information. The theory says the bound still holds."""
    def sc(case, known):
        return value
    return sc


def inverted(base: Scorer = handcrafted_scorer) -> Scorer:
    """
    s -> 1 - s. The least safe states score highest.

    Adversarial by construction. If the bound holds here it holds for any
    fixed score, because no fixed score can be worse than the exact negation
    of a good one.
    """
    def sc(case, known):
        return 1.0 - base(case, known)
    return sc


def band_shifted(base: Scorer, band: str, k: float) -> Scorer:
    """
    s -> s**(1/(1+k)) for cases in one income band, identity elsewhere.

    The instrument for round S, which causes the subgroup mechanism instead
    of observing it. Every other corruption above is applied to every case;
    this one is applied to one group, which is the whole point.

    Why this shape
    --------------
    `theory.md` §4 claims the subgroup failure comes from score **levels**
    differing between groups while the **ranking inside** each group is
    fine. Three properties make this transform a test of exactly that, and
    each is checkable before any run:

    **Monotone inside the band.** s**(1/(1+k)) is strictly increasing on
    [0, 1] for k > -1, so the order of the shifted band's states is
    untouched. Whatever the sweep produces cannot be added noise.

    **Not monotone across bands.** A state in the shifted band and one
    outside it can swap places, so the levels move between groups. That is
    the property under test and the only one that changes.

    **Identity at k = 0, and bounded.** `band_shifted(base, b, 0)` returns
    `base` exactly, giving a true control arm, and the image stays in
    [0, 1] for every k >= 0 so no score leaves its range.

    The direction matters: the exponent is below 1 for k > 0, which pushes
    scores **up**. The rule commits when the score clears the threshold, so
    inflating one band's scores makes it commit more often there —
    including on states it cannot decide. Overconfidence in one group is
    what is being injected.

    `band` is matched with `conditional.hardness`, which reads only
    `employment_income` — a field the agent knows at the opening state. A
    corruption keyed on something the rule cannot observe would be a
    different and less interesting experiment.
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    from .conditional import hardness

    power = 1.0 / (1.0 + k)

    def sc(case, known):
        s = base(case, known)
        if hardness(case) != band:
            return s
        return s ** power
    return sc


# ---------------------------------------------------------------------------
# The suite
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Corruption:
    name: str
    scorer: Scorer
    note: str


def suite(base: Scorer = handcrafted_scorer, seed: int = 13
          ) -> list[Corruption]:
    """
    The pre-registered set, in the pre-registered order.

    Fixed here rather than assembled at the call site so that the set cannot
    grow after the results are in. Adding a corruption later is visible as a
    change to this function.
    """
    return [
        Corruption("identity", identity(base), "control"),
        Corruption("coarse(0.1)", coarse(base, 0.1),
                   "rounds to tenths; imitates confidence clumping"),
        Corruption("sharpen(0.25)", sharpen(base, 0.25),
                   "monotone, so AUC is unchanged by construction"),
        Corruption("noisy(0.10)", noisy(base, 0.10, seed), "mild rank noise"),
        Corruption("noisy(0.25)", noisy(base, 0.25, seed), "moderate"),
        Corruption("noisy(0.50)", noisy(base, 0.50, seed), "severe"),
        Corruption("constant", constant(0.5), "carries no information"),
        Corruption("inverted", inverted(base),
                   "anti-correlated; the theory's worst case"),
    ]


def ordering_quality(cases: list[dict], scorer: Scorer) -> float:
    """
    AUC of the corrupted score over every knowledge state.

    Reported alongside each corruption so coverage can be read against rank
    quality rather than against the corruption's name. `sharpen` and
    `identity` should agree to within floating-point error; if they do not,
    the transform is not monotone and the experiment is mislabelled.
    """
    from .scorer import auc
    from .validate import states_of
    return auc([(scorer(c, k), determinable)
                for c, k, determinable in states_of(cases)])


def rank_correlation(cases: list[dict], a: Scorer, b: Scorer) -> float:
    """
    Kendall tau-b between two scorers over all knowledge states.

    Sharper than comparing AUCs: two scorers can share an AUC and order the
    states completely differently. Used to verify that `sharpen` really is
    order-preserving (tau = 1) rather than merely similar, and to quantify how
    much ordering each `noisy` level actually destroys.

    tau-b rather than tau-a because `coarse` creates ties deliberately, and a
    coefficient that ignores them would report the rounding as a bigger change
    than it is.
    """
    xs, ys = [], []
    from .validate import states_of
    for c, k, _ in states_of(cases):
        xs.append(a(c, k))
        ys.append(b(c, k))

    n = len(xs)
    con = dis = tx = ty = 0
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            if dx == 0 and dy == 0:
                tx += 1
                ty += 1
            elif dx == 0:
                tx += 1
            elif dy == 0:
                ty += 1
            elif (dx > 0) == (dy > 0):
                con += 1
            else:
                dis += 1

    total = n * (n - 1) / 2
    denom = math.sqrt((total - tx) * (total - ty))
    return (con - dis) / denom if denom > 0 else 0.0
