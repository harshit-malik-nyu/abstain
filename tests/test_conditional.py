"""
The per-stratum accounting, tested directly.

`conditional.py` decides what "the error budget is concentrated" means, and
the whole central finding is a reading of its output. It was at 42% coverage:
the parts exercised by an actual run were covered, and the parts that decide
*how a number is interpreted* — whether a subgroup is hidden, how
disproportion is measured, what an empty stratum does — were not.

Those are the parts where a quiet mistake changes a conclusion rather than
crashing, so they are pinned on hand-built inputs where the right answer is
known by construction rather than by running the method.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abstain.conditional import (BANDS, Breakdown, StratumTally, collector,
                                 hardness, population_shares,
                                 undetermined_share)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev():
    return json.loads((ROOT / "evidence" / "fine_dev.json").read_text())


def band(breakdown: Breakdown, name: str, *, deployed: int, unsafe: int,
         decidable: int = 0, resolved: int = 0, abstained: int = 0) -> None:
    t = breakdown.tally(name)
    t.deployed, t.unsafe = deployed, unsafe
    t.decidable, t.resolved, t.abstained = decidable, resolved, abstained


# ---------------------------------------------------------------------------
# The strata themselves
# ---------------------------------------------------------------------------

def test_the_bands_partition_every_income():
    """
    No income may fall outside the four bands, or cases would vanish from
    every breakdown without anything reporting that they had.
    """
    for income in range(0, 120_001, 500):
        case = {"household": {"employment_income": income}}
        assert hardness(case) in BANDS, income


def test_the_boundaries_are_where_the_first_commit_put_them():
    def at(income: int) -> str:
        return hardness({"household": {"employment_income": income}})

    assert at(6_000) == "well-below" and at(6_001) == "near-threshold"
    assert at(24_000) == "near-threshold" and at(24_001) == "above"
    assert at(36_000) == "above" and at(36_001) == "well-above"


# ---------------------------------------------------------------------------
# Rates over empty denominators
# ---------------------------------------------------------------------------

def test_an_untouched_stratum_reports_zero_rather_than_dividing_by_zero():
    t = StratumTally(band="well-below")
    assert t.unsafe_rate == 0.0
    assert t.coverage == 0.0
    assert t.as_dict()["deployed"] == 0


def test_an_empty_breakdown_has_no_worst_band():
    b = Breakdown(alpha=0.20)
    assert b.worst_band is None
    assert b.pooled_unsafe_rate == 0.0
    assert not b.hides_a_subgroup
    assert b.concentration == {}


def test_a_band_that_was_never_deployed_cannot_be_the_worst():
    """
    A 0/0 rate is 0.0, which would tie with a genuinely safe band — but a
    stratum nobody was deployed into is not evidence of anything.
    """
    b = Breakdown(alpha=0.20)
    band(b, "well-below", deployed=100, unsafe=30)
    band(b, "near-threshold", deployed=0, unsafe=0)
    assert b.worst_band == "well-below"
    assert b.concentration["near-threshold"] == 0.0


# ---------------------------------------------------------------------------
# hides_a_subgroup — the predicate the finding is stated in
# ---------------------------------------------------------------------------

def test_it_needs_the_pooled_rate_inside_budget_and_a_band_outside_it():
    b = Breakdown(alpha=0.20)
    band(b, "well-below", deployed=100, unsafe=40)   # 40%, over budget
    band(b, "well-above", deployed=900, unsafe=10)   # ~1%
    assert b.pooled_unsafe_rate < 0.20
    assert b.hides_a_subgroup


def test_a_pooled_rate_over_budget_is_not_hiding_anything():
    b = Breakdown(alpha=0.20)
    band(b, "well-below", deployed=100, unsafe=40)
    band(b, "well-above", deployed=100, unsafe=40)
    assert b.pooled_unsafe_rate > 0.20
    assert not b.hides_a_subgroup, \
        "a rule that is visibly over budget is broken, not misleading"


def test_an_evenly_spent_budget_hides_nothing():
    b = Breakdown(alpha=0.20)
    band(b, "well-below", deployed=500, unsafe=50)
    band(b, "well-above", deployed=500, unsafe=50)
    assert not b.hides_a_subgroup


def test_a_band_exactly_at_the_tolerance_does_not_count_as_over():
    """
    The predicate is strict, and it should be: holding exactly alpha is
    holding alpha.
    """
    b = Breakdown(alpha=0.20)
    band(b, "well-below", deployed=100, unsafe=20)
    band(b, "well-above", deployed=900, unsafe=0)
    assert not b.hides_a_subgroup


# ---------------------------------------------------------------------------
# concentration
# ---------------------------------------------------------------------------

def test_concentration_is_a_ratio_of_shares_not_a_rate():
    """
    A band holding 10% of deployments and 40% of unsafe commitments is at
    4.0, whatever the absolute rates are. Reporting the rate instead would
    make bands of different size incomparable, which is the whole reason the
    figure is a ratio.
    """
    b = Breakdown(alpha=0.20)
    band(b, "well-below", deployed=100, unsafe=40)
    band(b, "well-above", deployed=900, unsafe=60)
    assert b.concentration["well-below"] == pytest.approx(4.0)
    assert b.concentration["well-above"] == pytest.approx(2.0 / 3.0)


def test_concentration_is_zero_when_nothing_was_unsafe():
    b = Breakdown(alpha=0.20)
    band(b, "well-below", deployed=100, unsafe=0)
    assert b.concentration["well-below"] == 0.0


def test_the_concentrations_average_to_one_over_deployments():
    """
    An arithmetic identity worth asserting: weighted by deployment share the
    ratios must average to exactly 1, so a bug in either numerator or
    denominator shows up here rather than as a plausible-looking table.
    """
    b = Breakdown(alpha=0.20)
    band(b, "a", deployed=100, unsafe=40)
    band(b, "b", deployed=300, unsafe=20)
    band(b, "c", deployed=600, unsafe=40)
    total = sum(t.deployed for t in b.tallies.values())
    weighted = sum(b.concentration[name] * t.deployed / total
                   for name, t in b.tallies.items())
    assert weighted == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# The collector, against a real run
# ---------------------------------------------------------------------------

def test_the_collector_counts_every_deployed_case_once(dev):
    from abstain.scorer import handcrafted_scorer
    from abstain.validate import validate

    b = Breakdown(alpha=0.20)
    validate(dev[:200], handcrafted_scorer, alpha=0.20, trials=5, seed=31,
             calibration_share=0.30, on_trial=collector(b))

    assert b.trials == 5
    total = sum(t.deployed for t in b.tallies.values())
    assert total > 0
    for t in b.tallies.values():
        assert t.unsafe + t.resolved + t.abstained == t.deployed, t.band
        assert t.decidable <= t.deployed


def test_the_collector_reports_bands_in_the_canonical_order(dev):
    from abstain.scorer import handcrafted_scorer
    from abstain.validate import validate

    b = Breakdown(alpha=0.20)
    validate(dev, handcrafted_scorer, alpha=0.20, trials=3, seed=31,
             calibration_share=0.30, on_trial=collector(b))
    order = [row["band"] for row in b.as_dict()["bands"]]
    assert order == [x for x in BANDS if x in b.tallies]


# ---------------------------------------------------------------------------
# The population descriptions
# ---------------------------------------------------------------------------

def test_population_shares_sum_to_one(dev):
    shares = population_shares(dev)
    assert set(shares) == set(BANDS)
    assert sum(shares.values()) == pytest.approx(1.0)
    assert population_shares([]) == {}


def test_undetermined_share_only_counts_reachable_states(dev):
    """
    The rule always starts knowing income and only adds fields, so a state
    without income is unreachable. Including those would dilute the figure
    with states the rule can never be in.
    """
    shares = undetermined_share(dev)
    assert set(shares) == set(BANDS)
    assert all(0.0 <= v <= 1.0 for v in shares.values())

    # Recomputed the long way on one band, as a check on the filter.
    expected_num = expected_den = 0
    for case in dev:
        if hardness(case) != "well-below":
            continue
        for key, state in case["states"].items():
            if "employment_income" not in key.split("|"):
                continue
            expected_den += 1
            if state["label"] == "underdetermined":
                expected_num += 1
    assert shares["well-below"] == pytest.approx(expected_num / expected_den)


def test_undetermined_share_is_highest_where_the_scorer_is_most_wrong(dev):
    """
    Context for the central finding rather than a property of the code: the
    band that absorbs the budget is also among the most undetermined, so its
    failure is not that it was easy and got mishandled.
    """
    shares = undetermined_share(dev)
    assert shares["well-below"] > shares["well-above"]
