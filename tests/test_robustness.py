"""
The corruption study, and the safety bug it found.

The tests below are not about whether the corruptions are implemented
tidily. The first group pins a defect: the threshold the rule falls back to
when it declines to certify itself used to be reachable, and under a score
with a point mass at 1.0 the "most conservative" setting committed blind on
nearly every undetermined state. That is the kind of bug that comes back,
because 1.0 reads as the maximum of a [0, 1] range and the comparison is
`>=`. So it is pinned from both ends: the sentinel is strictly above 1.0, and
a scorer that returns exactly 1.0 everywhere commits nothing at it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from abstain.conditional import BANDS, hardness
from abstain.robustness import (constant, coarse, identity, inverted, noisy,
                                ordering_quality, rank_correlation, sharpen,
                                suite)
from abstain.rule import (INFEASIBLE_THRESHOLD, calibrate,
                          calibrate_on_trajectories, run_case)
from abstain.scorer import auc, handcrafted_scorer
from abstain.validate import states_of, validate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev():
    return json.loads((ROOT / "evidence" / "dev.json").read_text())


# ---------------------------------------------------------------------------
# The bug
# ---------------------------------------------------------------------------

def test_infeasible_threshold_is_above_any_legal_score():
    """
    Scores are contracted to [0, 1]. The refusal threshold must be outside it.

    Was 1.0, which is inside. `run_case` commits on `score >= threshold`, so
    the sentinel admitted every score that reached the top of its range.
    """
    assert INFEASIBLE_THRESHOLD > 1.0
    assert math.isfinite(INFEASIBLE_THRESHOLD), \
        "has to survive a JSON round-trip; infinity does not"


def test_a_score_pinned_at_one_commits_nothing_when_infeasible():
    """
    The behavioural form of the same check, which is the one that matters.

    A constant-1.0 scorer is the adversary: at the old sentinel it cleared
    the threshold at the opening state of every case and committed
    immediately.
    """
    case = {"id": 0, "household": {"employment_income": 20_000,
                                   "dependents": 1, "age": 40,
                                   "state_name": "NY"},
            "states": {}}
    # Every state undetermined, so any commitment is unsafe.
    import itertools
    fields = ("age", "dependents", "employment_income", "state_name")
    for r in range(len(fields) + 1):
        for known in itertools.combinations(fields, r):
            case["states"]["|".join(sorted(known))] = {
                "label": "underdetermined", "truth": "cannot_determine"}

    t = run_case(case, lambda c, k: 1.0, INFEASIBLE_THRESHOLD)
    assert not t.committed, \
        "the refusal threshold was cleared by a score of exactly 1.0"

    # And the old value is still demonstrably broken, so the test documents
    # the defect rather than only the fix.
    assert run_case(case, lambda c, k: 1.0, 1.0).committed


def test_both_calibrators_return_the_unreachable_sentinel(dev):
    """Infeasibility has one meaning, so it has one threshold."""
    hopeless = calibrate([(1.0, True)] * 40, alpha=0.01)
    assert not hopeless.feasible
    assert hopeless.threshold == INFEASIBLE_THRESHOLD

    traj = calibrate_on_trajectories(
        dev[:20], inverted(), lambda c, sc, tau: run_case(c, sc, tau),
        alpha=0.01)
    assert not traj.feasible
    assert traj.threshold == INFEASIBLE_THRESHOLD


def test_the_corruptions_that_found_it_really_do_reach_one(dev):
    """
    The bug was invisible because the primary scorer never reaches 1.0.

    Pinning the premise: `handcrafted_scorer` tops out below 1.0 on this
    benchmark, which is why 150 trials at four tolerances could not have
    caught it, and two of the corruptions do reach it.
    """
    rows = states_of(dev)
    top = max(handcrafted_scorer(c, k) for c, k, _ in rows)
    assert top < 1.0, (
        "if the primary scorer now reaches 1.0, the claim that the primary "
        "experiment could not have found this bug is no longer true")

    for sc in (inverted(), noisy(sigma=0.5, seed=13)):
        at_one = [d for c, k, d in rows if sc(c, k) >= 1.0]
        assert at_one, "corruption no longer exercises the sentinel"
        assert not all(at_one), \
            "and some of those states must be undetermined for it to be unsafe"


# ---------------------------------------------------------------------------
# The corruptions are what they are labelled
# ---------------------------------------------------------------------------

def test_sharpen_is_strictly_order_preserving(dev):
    """
    The claim that makes `sharpen` a probe rather than just another condition.

    If the transform is not order-preserving the experiment is mislabelled
    and B2 is testing something else.
    """
    base, sharp = identity(), sharpen()
    assert rank_correlation(dev, base, sharp) == pytest.approx(1.0)
    assert ordering_quality(dev, sharp) == pytest.approx(
        ordering_quality(dev, base), abs=1e-12)


def test_inverted_reverses_the_order(dev):
    assert rank_correlation(dev, identity(), inverted()) == pytest.approx(-1.0)
    assert ordering_quality(dev, inverted()) < 0.1


def test_constant_carries_no_information(dev):
    assert ordering_quality(dev, constant()) == pytest.approx(0.5)


def test_noise_degrades_ordering_monotonically(dev):
    """More noise, less ordering. A dial that is not monotone is not a dial."""
    taus = [rank_correlation(dev, identity(), noisy(sigma=s, seed=13))
            for s in (0.10, 0.25, 0.50)]
    assert taus == sorted(taus, reverse=True), taus


def test_coarse_creates_ties_without_destroying_order(dev):
    """Rounding should cost a little ordering and a lot of resolution."""
    rows = states_of(dev)
    fine = {handcrafted_scorer(c, k) for c, k, _ in rows}
    rounded = {coarse()(c, k) for c, k, _ in rows}
    assert len(rounded) < len(fine) / 5
    assert rank_correlation(dev, identity(), coarse()) > 0.9


def test_noisy_is_a_function_not_a_draw(dev):
    """
    The same state must score the same twice.

    The rule evaluates a state more than once — the greedy selector looks
    ahead, then the stopping rule scores where it landed. A score that
    changes between calls is not fixed, and the guarantee needs it to be, so
    a violation under a non-deterministic score would be attributable to the
    non-determinism rather than to the corruption.
    """
    sc = noisy(sigma=0.5, seed=13)
    for c, k, _ in states_of(dev)[:60]:
        assert sc(c, k) == sc(c, k)


def test_noisy_is_stable_across_processes(dev):
    """
    And the same twice in a *different interpreter*.

    The first implementation seeded from `hash()`, which Python salts per
    process, so the corrupted scorer was a different function on every run.
    Within one process the previous test passed and the experiment was still
    unreproducible, which is exactly why this one spawns a subprocess.
    """
    import subprocess
    import sys
    code = (
        "import json,sys;sys.path.insert(0,'src');"
        "from abstain.robustness import noisy;"
        "from abstain.validate import states_of;"
        "d=json.load(open('evidence/dev.json'));s=noisy(sigma=0.5,seed=13);"
        "print(repr([s(c,k) for c,k,_ in states_of(d)[:12]]))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    here = repr([noisy(sigma=0.5, seed=13)(c, k)
                 for c, k, _ in states_of(dev)[:12]])
    assert out.stdout.strip() == here


def test_the_suite_is_the_preregistered_set():
    """
    Eight conditions, in order, as `docs/preregistration-2.md` lists them.

    Pinned so that a corruption cannot be added or dropped after the results
    are in without the change showing up as a test failure.
    """
    names = [c.name for c in suite()]
    assert names == ["identity", "coarse(0.1)", "sharpen(0.25)",
                     "noisy(0.10)", "noisy(0.25)", "noisy(0.50)",
                     "constant", "inverted"]


# ---------------------------------------------------------------------------
# The guarantee is conditional on feasibility
# ---------------------------------------------------------------------------

def test_violation_rate_when_feasible_is_none_not_zero(dev):
    """
    A procedure that always declined has no guarantee to test.

    Reporting 0.0 there would read as a pass, which is the single most
    misleading number this module could produce.
    """
    v = validate(dev[:30], inverted(), alpha=0.05, trials=5, seed=1)
    assert v.infeasible_rate == 1.0
    assert v.violation_rate_when_feasible is None
    assert v.holds is None
    assert v.as_dict()["violation_rate_when_feasible"] is None


def test_feasible_and_pooled_violation_rates_are_both_reported(dev):
    v = validate(dev, handcrafted_scorer, alpha=0.10, trials=8, seed=11)
    d = v.as_dict()
    assert "violation_rate" in d and "violation_rate_when_feasible" in d
    assert d["feasible_trials"] <= d["trials"]


# ---------------------------------------------------------------------------
# Experiment C's premise
# ---------------------------------------------------------------------------

def test_strata_agree_with_the_split_script(dev):
    """
    `conditional.hardness` is a copy of `split.hardness`, pinned here.

    `scripts/split.py` is the first commit in this repository and its
    untouched state is the evidence that the split preceded the method, so it
    is not edited to export a helper. The duplication is only safe while this
    passes.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "split_under_test", ROOT / "scripts" / "split.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    cases = json.loads((ROOT / "evidence" / "cases.json").read_text())
    for c in cases:
        assert hardness(c) == mod.hardness(c), c["household"]
    assert set(BANDS) >= {hardness(c) for c in cases}


def test_the_scorer_ranks_well_inside_every_band(dev):
    """
    The mechanism behind experiment C, pinned as a premise.

    The finding is that good ranking in every subgroup does not give a
    threshold that is safe in every subgroup. That is only a finding if the
    ranking really is good in every subgroup, so this asserts the premise
    rather than leaving it to the write-up.
    """
    rows = states_of(dev)
    for b in BANDS:
        sub = [(handcrafted_scorer(c, k), d)
               for c, k, d in rows if hardness(c) == b]
        assert auc(sub) > 0.9, (b, auc(sub))


def test_score_levels_differ_across_bands(dev):
    """
    And the other half of the mechanism: the distributions are shifted.

    Undetermined states in `well-below` score materially higher than
    undetermined states in `near-threshold`, so one horizontal threshold cuts
    the two bands at different quantiles. Without this, concentration would
    need a different explanation.
    """
    rows = states_of(dev)

    def mean_open(band):
        xs = [handcrafted_scorer(c, k) for c, k, d in rows
              if hardness(c) == band and not d]
        return sum(xs) / len(xs)

    assert mean_open("well-below") > 1.5 * mean_open("near-threshold")
