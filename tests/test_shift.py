"""
The shift harness, tested directly rather than only through its results.

Why this file exists
--------------------
`shift.py` produced the most dramatic number in the repository — a pooled rule
going from 0.7% to 98% violations while its reported bound never moves — and
it had **no unit tests at all**. Coverage said 0%.

The evidence-coupling tests check that the write-up matches
`evidence/round5_shift.json`, which is a different thing: they would pass
unchanged if a refactor broke the harness, because they compare prose to a
file rather than code to behaviour. The file is only re-generated when someone
re-runs a forty-minute experiment.

So the resampling, the pairing, and the summary statistics are pinned here.
The harness's own limitations — the ones reported alongside the result — are
pinned too, because a limitation that stops being true should force the
write-up to change.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from abstain.conditional import hardness
from abstain.scorer import handcrafted_scorer
from abstain.shift import (ShiftPoint, natural_share, reweight,
                           sanity_unshifted, sweep_shift)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev():
    return json.loads((ROOT / "evidence" / "fine_dev.json").read_text())


# ---------------------------------------------------------------------------
# reweight
# ---------------------------------------------------------------------------

def test_it_hits_the_target_share(dev):
    rng = random.Random(1)
    for target in (0.143, 0.25, 0.5, 0.8, 1.0):
        out = reweight(dev, "well-below", target, rng)
        got = sum(1 for c in out if hardness(c) == "well-below") / len(out)
        assert got == pytest.approx(target, abs=1.0 / len(out))


def test_it_keeps_the_fold_the_same_size(dev):
    """
    The alternative — discarding cases from other bands until the ratio comes
    out — shrinks the fold as the shift grows and confounds the shift with
    sample size. That confound is the reason this resamples instead.
    """
    rng = random.Random(1)
    for target in (0.143, 0.5, 1.0):
        assert len(reweight(dev, "well-below", target, rng)) == len(dev)


def test_it_honours_an_explicit_size(dev):
    rng = random.Random(1)
    assert len(reweight(dev, "well-below", 0.5, rng, size=100)) == 100


def test_a_target_of_zero_excludes_the_band(dev):
    rng = random.Random(1)
    out = reweight(dev, "well-below", 0.0, rng)
    assert out and not any(hardness(c) == "well-below" for c in out)


def test_it_refuses_an_impossible_share(dev):
    with pytest.raises(ValueError):
        reweight(dev, "well-below", 1.5, random.Random(1))
    with pytest.raises(ValueError):
        reweight(dev, "well-below", -0.1, random.Random(1))


def test_it_returns_empty_rather_than_guessing(dev):
    """
    A band with no cases cannot be resampled to any positive share, and
    returning a fold without it would silently answer a different question.
    """
    only_one_band = [c for c in dev if hardness(c) == "well-above"]
    assert reweight(only_one_band, "well-below", 0.5,
                    random.Random(1)) == []
    # And the reverse: asking for less than 100% of a pool that has only one
    # band leaves nothing to fill the remainder with.
    assert reweight(only_one_band, "well-above", 0.5,
                    random.Random(1)) == []


def test_it_is_deterministic_for_a_given_stream(dev):
    a = reweight(dev, "well-below", 0.6, random.Random(7))
    b = reweight(dev, "well-below", 0.6, random.Random(7))
    assert [c["id"] for c in a] == [c["id"] for c in b]


def test_the_distinct_case_count_falls_as_the_shift_grows(dev):
    """
    The harness limitation reported alongside the result.

    Forcing a 14.3% band to 80% of a fold needs replacement, so the
    high-shift rows rest on fewer distinct cases. If that ever stopped being
    true the write-up would be carrying a caveat it no longer needs.
    """
    rng = random.Random(3)
    counts = [len({c["id"] for c in reweight(dev, "well-below", t, rng)})
              for t in (0.143, 0.40, 0.80, 1.00)]
    assert counts == sorted(counts, reverse=True), counts
    # At a full shift there is nothing but that band's own cases.
    assert counts[-1] == sum(1 for c in dev if hardness(c) == "well-below")


def test_natural_share_matches_the_benchmark(dev):
    assert natural_share(dev, "well-below") == pytest.approx(0.1429, abs=1e-3)
    assert natural_share([], "well-below") == 0.0


# ---------------------------------------------------------------------------
# ShiftPoint's summary statistics
# ---------------------------------------------------------------------------

def _point(bands: dict[str, tuple[int, int]], alpha: float = 0.20
           ) -> ShiftPoint:
    p = ShiftPoint(scheme="pooled", alpha=alpha, target_share=0.143)
    for name, (deployed, unsafe) in bands.items():
        t = p.tally(name)
        t["deployed"], t["unsafe"] = deployed, unsafe
    return p


def test_hides_a_subgroup_needs_both_halves():
    """
    True only when the pooled rate is inside budget and a band is outside it.
    Either half alone is a different situation.
    """
    # Pooled 5%, one band at 40%: the case the repository is about.
    assert _point({"a": (100, 40), "b": (900, 10)}).hides_a_subgroup

    # Pooled over budget: not hidden, just broken.
    assert not _point({"a": (100, 40), "b": (900, 400)}).hides_a_subgroup

    # Every band inside budget: nothing hidden.
    assert not _point({"a": (100, 10), "b": (900, 90)}).hides_a_subgroup


def test_worst_band_rate_ignores_bands_that_were_never_deployed():
    p = _point({"a": (100, 40), "empty": (0, 0)})
    assert p.worst_band_rate == pytest.approx(0.40)


def test_concentration_is_one_when_the_budget_is_spread_evenly():
    p = _point({"a": (500, 50), "b": (500, 50)})
    assert p.max_concentration == pytest.approx(1.0)


def test_concentration_rises_with_disproportion():
    even = _point({"a": (500, 50), "b": (500, 50)}).max_concentration
    skewed = _point({"a": (500, 90), "b": (500, 10)}).max_concentration
    assert skewed > even


def test_an_empty_point_reports_nothing_rather_than_zero():
    p = ShiftPoint(scheme="pooled", alpha=0.20, target_share=0.143)
    assert p.violation_rate is None
    assert p.max_concentration == 0.0
    assert p.worst_band_rate == 0.0
    assert not p.hides_a_subgroup
    assert p.distinct_fraction == 0.0


def test_the_reported_dict_carries_every_field_the_writeup_uses():
    d = _point({"a": (100, 40), "b": (900, 10)}).as_dict()
    for key in ("violation_rate", "mean_unsafe_rate", "mean_coverage",
                "mean_reported_bound", "distinct_fraction",
                "worst_band_rate", "max_concentration",
                "hides_a_subgroup", "bands"):
        assert key in d, key


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------

def test_both_schemes_see_the_same_folds(dev):
    """
    The comparison is paired, so a difference between schemes cannot be a
    difference in which cases they happened to get.

    Checked through `distinct_fraction`: the two schemes are given the same
    reweighted deployment fold in every trial, so the number of distinct
    cases behind each must agree exactly.
    """
    sw = sweep_shift(dev, handcrafted_scorer, shares=(0.40,),
                     schemes=("pooled", "by-band"), alphas=(0.20,),
                     trials=4, seed=41)
    pooled = next(p for p in sw.points if p.scheme == "pooled")
    band = next(p for p in sw.points if p.scheme == "by-band")
    assert pooled.deployed_sum == band.deployed_sum
    assert pooled.distinct_sum == band.distinct_sum


def test_the_sweep_records_whether_calibration_was_shifted(dev):
    for recal in (False, True):
        sw = sweep_shift(dev, handcrafted_scorer, shares=(0.40,),
                         schemes=("pooled",), alphas=(0.20,), trials=2,
                         seed=41, shift_calibration=recal)
        assert sw.shift_calibration is recal
        assert sw.as_dict()["shift_calibration"] is recal


def test_recalibration_changes_the_outcome_at_a_heavy_shift(dev):
    """
    If `shift_calibration` did nothing, the addendum's whole result would be
    an artefact of a flag that was never wired up.
    """
    common = dict(shares=(1.00,), schemes=("pooled",), alphas=(0.20,),
                  trials=6, seed=41)
    stale = sweep_shift(dev, handcrafted_scorer, **common,
                        shift_calibration=False).points[0]
    fresh = sweep_shift(dev, handcrafted_scorer, **common,
                        shift_calibration=True).points[0]
    assert stale.violation_rate is not None
    assert fresh.violation_rate is not None
    assert fresh.violation_rate < stale.violation_rate


def test_monotone_reports_what_it_claims(dev):
    sw = sweep_shift(dev, handcrafted_scorer, shares=(0.143, 0.60, 1.00),
                     schemes=("pooled",), alphas=(0.20,), trials=4, seed=41)
    rates = [p.violation_rate or 0.0
             for p in sorted(sw.for_scheme("pooled", 0.20),
                             key=lambda p: p.target_share)]
    assert sw.monotone("pooled", 0.20) == (rates == sorted(rates))


def test_for_scheme_filters_on_both_scheme_and_alpha(dev):
    sw = sweep_shift(dev, handcrafted_scorer, shares=(0.40,),
                     schemes=("pooled", "by-band"), alphas=(0.20, 0.15),
                     trials=2, seed=41)
    got = sw.for_scheme("pooled", 0.20)
    assert len(got) == 1
    assert got[0].scheme == "pooled" and got[0].alpha == 0.20


def test_the_control_agrees_with_the_ordinary_validation_path(dev):
    """
    F1's control. If the harness at the natural share disagrees with
    `validate`, the sweep is measuring the harness rather than the shift.
    """
    ordinary = sanity_unshifted(dev, handcrafted_scorer, alpha=0.20,
                                trials=12, seed=41)
    sw = sweep_shift(dev, handcrafted_scorer,
                     shares=(natural_share(dev, "well-below"),),
                     schemes=("pooled",), alphas=(0.20,), trials=12,
                     seed=41)
    harness = sw.points[0]

    assert ordinary["violation_rate_when_feasible"] is not None
    assert harness.violation_rate is not None
    # Both should be small; the resampling makes them not identical, so the
    # check is that neither is anywhere near the tolerance.
    assert ordinary["violation_rate_when_feasible"] <= 0.10
    assert harness.violation_rate <= 0.10
    assert harness.as_dict()["mean_coverage"] == pytest.approx(
        ordinary["mean_coverage"], abs=0.12)
