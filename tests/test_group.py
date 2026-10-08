"""
Group-conditional calibration, and the arithmetic that says when to trust it.

The tests here split into two kinds. The first kind checks that the grouped
calibrator does what it says — conjunctive feasibility, no silent fallback to
another group's threshold, a paired draw against the pooled arm. The second
kind pins the power arithmetic, because the conclusion of round three is that
the experiment was underpowered, and a claim of underpowered-ness is worth
exactly as much as the numbers behind it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from abstain.conditional import BANDS, hardness
from abstain.group import (SCHEMES, POST_HOC, by_band, calibrate_by_group,
                           evaluate_by_group, minimum_calibration_size,
                           pooled, reachable_alpha, separate_well_below,
                           validate_groups)
from abstain.power import (calibration_cases_needed, deployment_cases_needed,
                           requirement, resolution, shortfall)
from abstain.rule import INFEASIBLE_THRESHOLD, clopper_pearson_upper
from abstain.scorer import handcrafted_scorer
from abstain.validate import trial_split

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev():
    return json.loads((ROOT / "evidence" / "dev.json").read_text())


# ---------------------------------------------------------------------------
# The draw is shared, so the comparison is paired
# ---------------------------------------------------------------------------

def test_trial_split_is_deterministic_and_disjoint(dev):
    a = trial_split(dev, trial=7, seed=23)
    b = trial_split(dev, trial=7, seed=23)
    assert [c["id"] for c in a[1]] == [c["id"] for c in b[1]]
    assert [c["id"] for c in a[2]] == [c["id"] for c in b[2]]

    cal_ids = {c["id"] for c in a[1]}
    dep_ids = {c["id"] for c in a[2]}
    assert not (cal_ids & dep_ids)
    assert len(cal_ids) + len(dep_ids) == len(dev)


def test_different_trials_draw_differently(dev):
    one = [c["id"] for c in trial_split(dev, trial=0, seed=23)[1]]
    two = [c["id"] for c in trial_split(dev, trial=1, seed=23)[1]]
    assert one != two


def test_the_pooled_scheme_reproduces_a_single_threshold(dev):
    """
    `pooled` is the ungrouped rule expressed in the grouped interface.

    If it does not collapse to one group, the comparison between schemes is
    comparing two implementations rather than two schemes.
    """
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="pooled",
                             alpha=0.20)
    assert list(cal.thresholds) == ["all"]
    assert {pooled(c) for c in dev} == {"all"}


def test_calibration_size_is_absolute_when_asked(dev):
    _, cal, dep = trial_split(dev, trial=3, seed=23, calibration_size=40)
    assert len(cal) == 40
    assert len(dep) == len(dev) - 40


# ---------------------------------------------------------------------------
# Feasibility is conjunctive, and absence is not a fallback
# ---------------------------------------------------------------------------

def test_one_infeasible_group_makes_the_whole_calibration_infeasible(dev):
    """
    A rule that holds the tolerance in three bands and not the fourth does
    not hold the tolerance. Reporting it as a partial pass would reintroduce
    the averaging this module exists to remove.
    """
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="by-band",
                             alpha=0.10)
    if cal.groups_feasible < len(cal.per_group):
        assert not cal.feasible
    # And the converse, so the property is pinned in both directions.
    assert cal.feasible == all(g["feasible"]
                               for g in cal.per_group.values())


def test_an_unseen_group_gets_the_refusal_threshold_not_a_borrowed_one(dev):
    """
    Falling back to another group's threshold is the exact substitution that
    produced the 19.2% band. Doing it silently in the module written to fix
    that would be worse than not writing the module.
    """
    only_one_band = [c for c in dev if hardness(c) == "well-above"][:12]
    assert only_one_band
    cal = calibrate_by_group(only_one_band, handcrafted_scorer,
                             scheme="by-band", alpha=0.35)

    other = next(c for c in dev if hardness(c) == "near-threshold")
    assert cal.threshold_for(other) == INFEASIBLE_THRESHOLD


def test_delta_is_not_split_across_groups(dev):
    """
    Each group's bound is a separate statement at delta about that group.

    A simultaneous statement over all groups would need delta/|groups| and be
    more conservative; the per-group form is what group-conditional validity
    means and what an operator asking "is this safe for this applicant"
    wants. Pinned so the choice is deliberate rather than incidental.
    """
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="by-band",
                             alpha=0.35, delta=0.05)
    for g in cal.per_group.values():
        if g["feasible"]:
            assert g["delta"] == pytest.approx(0.05)


def test_schemes_are_registered_and_the_post_hoc_one_is_flagged():
    assert set(SCHEMES) == {"pooled", "by-band", "separate-well-below"}
    assert POST_HOC == {"separate-well-below"}
    assert separate_well_below.__doc__ and "post-hoc" in \
        separate_well_below.__doc__.lower(), \
        "the scheme chosen after seeing which band failed has to say so"


def test_the_post_hoc_flag_reaches_the_reported_dict(dev):
    v = validate_groups(dev, handcrafted_scorer,
                        scheme="separate-well-below", alpha=0.35, trials=3,
                        seed=23)
    assert v.as_dict()["post_hoc"] is True
    w = validate_groups(dev, handcrafted_scorer, scheme="by-band",
                        alpha=0.35, trials=3, seed=23)
    assert w.as_dict()["post_hoc"] is False


def test_by_band_covers_every_band(dev):
    assert {by_band(c) for c in dev} <= set(BANDS)


# ---------------------------------------------------------------------------
# Deployment accounting
# ---------------------------------------------------------------------------

def test_group_counts_sum_to_the_pooled_counts(dev):
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="by-band",
                             alpha=0.35)
    res = evaluate_by_group(dev[40:], handcrafted_scorer, cal)
    assert sum(g["deployed"] for g in res.by_group.values()) == res.n
    assert sum(g["unsafe"] for g in res.by_group.values()) == res.unsafe
    assert res.unsafe + res.resolved + res.abstained == res.n


def test_worst_group_rate_is_at_least_the_pooled_rate(dev):
    """
    A maximum over groups cannot fall below the pooled average of them.

    Trivially true and worth asserting: it is the inequality the whole
    experiment turns on, and a bug in the accounting would most likely show
    up as this being violated.
    """
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="by-band",
                             alpha=0.35)
    res = evaluate_by_group(dev[40:], handcrafted_scorer, cal)
    assert res.worst_group_rate >= res.unsafe_rate - 1e-12


def test_validation_reports_none_when_nothing_was_feasible(dev):
    """Same discipline as `Validation`: no feasible trial, no rate."""
    v = validate_groups(dev, handcrafted_scorer, scheme="by-band",
                        alpha=0.05, trials=4, seed=23)
    assert v.infeasible_rate == 1.0
    assert v.violation_rate_when_feasible is None
    assert v.group_violation_rate_when_feasible is None


# ---------------------------------------------------------------------------
# The power arithmetic
# ---------------------------------------------------------------------------

def test_the_calibration_floor_matches_the_bound_it_came_from():
    """
    The closed form and the exact bound have to agree.

        n >= ln(delta) / ln(1 - alpha)

    derived from 1 - delta**(1/n) <= alpha. If the algebra is wrong the whole
    power analysis is, so it is checked against `clopper_pearson_upper`
    directly rather than trusted.
    """
    for alpha in (0.40, 0.35, 0.30, 0.20, 0.15, 0.10, 0.05):
        n = calibration_cases_needed(alpha, 0.05)
        assert clopper_pearson_upper(0, n, 0.05) <= alpha + 1e-12
        assert clopper_pearson_upper(0, n - 1, 0.05) > alpha, \
            f"n={n} is not minimal at alpha={alpha}"


def test_power_and_group_modules_share_one_floor():
    """
    `power.calibration_cases_needed` and `group.minimum_calibration_size` are
    the same formula in two places. Pinned equal so the analysis and the
    calibrator cannot disagree about the constraint they share.
    """
    for alpha in (0.40, 0.30, 0.20, 0.15, 0.10, 0.05):
        assert calibration_cases_needed(alpha) == \
            minimum_calibration_size(alpha)


def test_reachable_alpha_inverts_the_floor():
    """
    The bisection agrees with the closed form to the floating-point bit.

    Note what is *not* asserted: that
    `calibration_cases_needed(reachable_alpha(n)) == n`. The inverse lands
    exactly on an integer boundary, so a discrepancy of 5.6e-17 in alpha
    tips `ceil` to n + 1 — measured, at n = 20 and n = 29. That round trip is
    unstable by construction rather than by error, and an assertion that
    depends on which side of an exact boundary a float falls would be
    pinning luck.
    """
    for n in (7, 10, 20, 29, 59):
        a = reachable_alpha(n)
        assert a == pytest.approx(1 - 0.05 ** (1 / n), abs=1e-12)
        # The substantive property: n cases certify this alpha.
        assert clopper_pearson_upper(0, n, 0.05) <= a + 1e-12
        assert calibration_cases_needed(a) <= n + 1


def test_the_published_floor_table_is_what_the_code_computes():
    """
    The table in `docs/preregistration-3.md` and `group.py`'s docstring.

    Numbers quoted in prose drift away from the code that produced them. This
    is the cheapest possible defence.
    """
    assert [round(reachable_alpha(n) * 100, 1) for n in (7, 10, 20, 29)] == \
        [34.8, 25.9, 13.9, 9.8]
    assert calibration_cases_needed(0.10) == 29


def test_resolution_is_the_reason_round_three_could_not_answer():
    """
    Eight deployed cases per band cannot resolve a 10% tolerance.

    0/8 and 1/8 are 0% and 12.5%; 10% lies between them. The question "did
    this band exceed 10%" has no answer at that sample size, and round three
    asked it.
    """
    assert resolution(8) == pytest.approx(0.125)
    assert resolution(8) > 0.10
    assert resolution(100) < 0.10


def test_deployment_requirement_grows_as_the_tolerance_tightens():
    needs = [deployment_cases_needed(a, 0.05) for a in (0.30, 0.20, 0.15)]
    assert needs == sorted(needs), needs


def test_the_requirement_is_driven_by_the_smallest_group():
    """
    Feasibility is conjunctive, so the group with fewest cases binds.

    A requirement computed from the average share would understate it, which
    is the mistake that makes an underpowered design look adequate.
    """
    tight = requirement(0.10, smallest_group_share=0.10)
    loose = requirement(0.10, smallest_group_share=0.25)
    assert tight.cases_needed > loose.cases_needed


def test_the_original_benchmark_is_short_at_the_headline_tolerance():
    """
    160 cases against what alpha = 0.10 needs.

    Stated as a test so the claim in the write-up is the claim in the code.
    """
    s = shortfall(160, 0.10)
    assert not s["adequate"]
    assert s["factor_short"] > 5


def test_the_fine_grid_clears_the_headline_tolerance():
    """
    1,344 households is the complete enumeration of the refined income grid,
    and it is what makes the alpha = 0.10 question answerable at all.
    """
    assert shortfall(1_344, 0.10)["adequate"]
    assert shortfall(640, 0.10)["adequate"] is False, \
        "640 was the coarse grid's ceiling and was not enough"


def test_requirement_rejects_impossible_arguments():
    for bad in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            calibration_cases_needed(bad)
        with pytest.raises(ValueError):
            deployment_cases_needed(0.10, bad)


def test_fine_grid_contains_the_coarse_one():
    """
    The refinement has to be a superset, or the two benchmarks are different
    populations and the primary result is not comparable to anything measured
    on the new one.
    """
    coarse = {0, 6_000, 12_000, 18_000, 21_000, 24_000, 30_000, 36_000,
              48_000, 60_000}
    fine = set(range(0, 60_001, 3_000))
    assert coarse <= fine
    assert len(fine) * 4 * 4 * 4 == 1_344
    assert all(v % 3_000 == 0 for v in coarse)


def test_requirement_total_uses_the_binding_side_not_the_sum():
    r = requirement(0.15)
    from_cal = r.calibration_total / r.calibration_share
    from_dep = r.deployment_total / (1 - r.calibration_share)
    assert r.cases_needed == math.ceil(max(from_cal, from_dep))


def test_the_default_calibration_share_is_wrong_for_this_experiment():
    """
    The finding this test was written to deny.

    It originally asserted `cases_needed < calibration_total +
    deployment_total`, on the reasoning that two folds drawn from one pool
    cost less than their sum. At alpha = 0.15 the numbers are 500 against
    295, and the assertion failed.

    The reason is a real design defect rather than a bug: the pool is split
    60/40, and group conditioning inflates the *deployment* requirement far
    harder than the calibration one, because a per-band rate now has to be
    resolvable in every band. A share tuned for pooled validation starves
    the side that matters, and at alpha = 0.15 that costs 1.7x the cases.
    """
    r = requirement(0.15)
    assert r.cases_needed > r.cases_needed_at_best_share
    assert r.share_penalty > 1.5
    assert r.best_calibration_share < 0.5, \
        "the deployment fold is the binding one, so it should get the larger share"


def test_the_best_share_makes_both_constraints_bind():
    """At the optimum the pool is exactly the sum and nothing is slack."""
    for alpha in (0.20, 0.15, 0.10):
        r = requirement(alpha)
        s = r.best_calibration_share
        n = r.cases_needed_at_best_share
        assert n == r.calibration_total + r.deployment_total
        assert s * n == pytest.approx(r.calibration_total)
        assert (1 - s) * n == pytest.approx(r.deployment_total)


# ---------------------------------------------------------------------------
# The measurement partition, and the comparison it inverted
# ---------------------------------------------------------------------------

def test_the_pooled_scheme_is_still_measured_on_bands(dev):
    """
    The defect that inverted round four's headline comparison.

    `evaluate_by_group` used one parameter for two jobs: which threshold a
    case is judged against, and how the results are broken down. Under
    `scheme="pooled"` there is a single calibration group, so bucketing
    results by it gave one bucket — `worst_group_rate` returned the pooled
    rate and `max_concentration` was 1.00 by construction.

    The reported numbers at alpha = 0.20 were a worst group of 11.1% and a
    concentration of 1.00 for the pooled rule, against 12.9% and 1.80 for the
    grouped one. That reads as group conditioning making things worse on the
    exact axis it was built to improve, and it was an artefact of measuring
    the two schemes against different partitions.
    """
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="pooled",
                             alpha=0.20)
    res = evaluate_by_group(dev[40:], handcrafted_scorer, cal)

    assert cal.scheme == "pooled"
    assert res.measured_by == "by-band"
    assert len(res.by_group) > 1, (
        "a pooled calibration must still be broken down by band, or the "
        "comparison between schemes is not a comparison")


def test_concentration_is_not_trivially_one_for_the_pooled_scheme(dev):
    """
    Concentration over a single bucket is 1.00 by definition and says nothing.

    If this ever reads exactly 1.00 again for the pooled scheme while unsafe
    commitments exist, the partitions have been collapsed back together.
    """
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="pooled",
                             alpha=0.20)
    res = evaluate_by_group(dev[40:], handcrafted_scorer, cal)
    if res.unsafe:
        assert res.max_concentration != 1.0


def test_every_scheme_is_scored_against_the_same_partition(dev):
    """
    The property that makes the scheme comparison meaningful.

    Deployment counts per band must be identical across schemes on the same
    cases — only the thresholds differ. If the per-band denominators move
    between schemes, the rates are not comparable.
    """
    deployed = {}
    for scheme in ("pooled", "by-band", "separate-well-below"):
        cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme=scheme,
                                 alpha=0.35)
        res = evaluate_by_group(dev[40:], handcrafted_scorer, cal)
        deployed[scheme] = {g: v["deployed"] for g, v in res.by_group.items()}

    first = deployed["pooled"]
    for scheme, counts in deployed.items():
        assert counts == first, (scheme, counts, first)


def test_the_recorded_threshold_comes_from_the_calibration_partition(dev):
    """
    Each band records the threshold its cases were actually judged against.

    Under a pooled calibration measured on bands, every band's recorded
    threshold is the single pooled one. Looking it up by the measurement
    group would silently report the refusal threshold instead, because no
    calibration group is named after a band.
    """
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="pooled",
                             alpha=0.20)
    res = evaluate_by_group(dev[40:], handcrafted_scorer, cal)
    recorded = {v["threshold"] for v in res.by_group.values()}
    assert recorded == {cal.thresholds["all"]}
    assert INFEASIBLE_THRESHOLD not in recorded or not cal.feasible


def test_measure_by_rejects_an_unknown_partition(dev):
    cal = calibrate_by_group(dev[:40], handcrafted_scorer, scheme="pooled",
                             alpha=0.20)
    with pytest.raises(ValueError):
        evaluate_by_group(dev[40:], handcrafted_scorer, cal,
                          measure_by="not-a-scheme")
