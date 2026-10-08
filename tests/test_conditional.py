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

from abstain.conditional import (BANDS, Breakdown, StratumTally,
                                 bootstrap_all_bands, bootstrap_band_rate,
                                 collector, hardness, population_shares,
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


# ---------------------------------------------------------------------------
# The cluster bootstrap
# ---------------------------------------------------------------------------

def per_case(*rows: tuple[str, str, int, int]) -> dict:
    """(case_id, band, deployed, unsafe) tuples as the collector would store."""
    return {cid: {"band": band, "deployed": d, "unsafe": u}
            for cid, band, d, u in rows}


def test_the_point_estimate_is_the_pooled_rate():
    pc = per_case(("a", "well-below", 100, 40), ("b", "well-below", 100, 60))
    out = bootstrap_band_rate(pc, "well-below", draws=200)
    assert out["point"] == pytest.approx(0.5)
    assert out["cases"] == 2
    assert out["observations"] == 200


def test_the_interval_brackets_the_point():
    pc = per_case(*[(f"c{i}", "above", 50, i % 7) for i in range(40)])
    out = bootstrap_band_rate(pc, "above", draws=800)
    assert out["lo"] <= out["point"] <= out["hi"]


def test_it_resamples_cases_not_observations():
    """
    The property the whole function exists for.

    Two cases, one always unsafe and one never, each deployed 500 times.
    Resampling *observations* would give a tight interval around 0.5 —
    250,000 coin flips. Resampling *cases* must give something close to
    {0, 0.5, 1}, because there are only two units of real variation.
    """
    pc = per_case(("always", "well-below", 500, 500),
                  ("never", "well-below", 500, 0))
    out = bootstrap_band_rate(pc, "well-below", draws=4_000)

    assert out["point"] == pytest.approx(0.5)
    assert out["lo"] == pytest.approx(0.0, abs=1e-9)
    assert out["hi"] == pytest.approx(1.0, abs=1e-9)

    # The claim is the RATIO, not either width on its own. A first version
    # asserted the naive halfwidth was under 0.01; at n = 1,000 and p = 0.5
    # it is genuinely 0.031, and the test was wrong rather than the code.
    # What matters is that treating observations as independent understates
    # the uncertainty by more than an order of magnitude.
    assert out["clustered_halfwidth"] > 0.4
    assert out["clustered_halfwidth"] > 10 * out["naive_halfwidth"]


def test_more_clusters_give_a_tighter_interval():
    """
    Same pooled rate and same total observations, different numbers of
    distinct cases. The interval must narrow as the real support grows.
    """
    few = per_case(*[(f"f{i}", "above", 200, 100) if i % 2 else
                     (f"f{i}", "above", 200, 0) for i in range(4)])
    many = per_case(*[(f"m{i}", "above", 20, 10) if i % 2 else
                      (f"m{i}", "above", 20, 0) for i in range(40)])

    a = bootstrap_band_rate(few, "above", draws=2_000)
    b = bootstrap_band_rate(many, "above", draws=2_000)
    assert a["observations"] == b["observations"]
    assert a["clustered_halfwidth"] > b["clustered_halfwidth"]


def test_it_is_deterministic_for_a_seed():
    pc = per_case(*[(f"c{i}", "above", 30, i % 5) for i in range(25)])
    a = bootstrap_band_rate(pc, "above", draws=500, seed=4)
    b = bootstrap_band_rate(pc, "above", draws=500, seed=4)
    c = bootstrap_band_rate(pc, "above", draws=500, seed=5)
    assert (a["lo"], a["hi"]) == (b["lo"], b["hi"])
    assert (a["lo"], a["hi"]) != (c["lo"], c["hi"])


def test_a_band_with_no_cases_reports_zero_rather_than_raising():
    out = bootstrap_band_rate(per_case(("a", "above", 10, 1)), "well-below")
    assert out["cases"] == 0
    assert out["point"] == out["lo"] == out["hi"] == 0.0


def test_a_narrower_level_gives_a_narrower_interval():
    pc = per_case(*[(f"c{i}", "above", 40, i % 6) for i in range(30)])
    wide = bootstrap_band_rate(pc, "above", draws=2_000, level=0.99)
    tight = bootstrap_band_rate(pc, "above", draws=2_000, level=0.80)
    assert (wide["hi"] - wide["lo"]) > (tight["hi"] - tight["lo"])


def test_all_bands_returns_only_the_ones_present():
    pc = per_case(("a", "well-below", 10, 1), ("b", "above", 10, 2))
    got = bootstrap_all_bands(pc, draws=100)
    assert [r["band"] for r in got] == ["well-below", "above"]


def test_the_collector_records_per_case_counts(dev):
    """
    The bootstrap is only meaningful if the structure it needs is real.
    """
    from abstain.scorer import handcrafted_scorer
    from abstain.validate import validate

    b = Breakdown(alpha=0.20)
    validate(dev[:300], handcrafted_scorer, alpha=0.20, trials=6, seed=31,
             calibration_share=0.30, on_trial=collector(b))

    assert b.per_case, "no per-case structure recorded"
    for cid, rec in b.per_case.items():
        assert rec["band"] in BANDS
        assert 0 <= rec["unsafe"] <= rec["deployed"]

    # The per-case counts must sum to the band tallies, or the two views
    # disagree about the same run.
    for band, tally in b.tallies.items():
        rows = [r for r in b.per_case.values() if r["band"] == band]
        assert sum(r["deployed"] for r in rows) == tally.deployed, band
        assert sum(r["unsafe"] for r in rows) == tally.unsafe, band


def test_observations_outnumber_cases_on_the_real_benchmark(dev):
    """
    The premise of the whole section: a case is deployed many times.
    """
    from abstain.scorer import handcrafted_scorer
    from abstain.validate import validate

    b = Breakdown(alpha=0.20)
    validate(dev, handcrafted_scorer, alpha=0.20, trials=20, seed=31,
             calibration_share=0.30, on_trial=collector(b))

    total = sum(r["deployed"] for r in b.per_case.values())
    assert total > 5 * len(b.per_case)
