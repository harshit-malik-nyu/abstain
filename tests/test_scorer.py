"""
Tests for the scorer.

The scorer is where coverage lives, not where the guarantee lives. These
check that it uses only what the agent can see, and that the ordering it
produces is what gets measured.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abstain.scorer import (
    FittedScorer, auc, constant_scorer, features, handcrafted_scorer,
)

ROOT = Path(__file__).resolve().parents[1]

CASE = {"id": 0,
        "household": {"employment_income": 20_000, "dependents": 1,
                      "age": 35, "state_name": "NY"},
        "states": {}}


class TestFeaturesUseOnlyWhatIsKnown:

    def test_an_unknown_field_does_not_leak_its_value(self):
        """
        The whole construction fails if the score can see a field the agent
        has not been told. Two cases differing only in an unknown field must
        score identically.
        """
        a = dict(CASE, household=dict(CASE["household"], dependents=0))
        b = dict(CASE, household=dict(CASE["household"], dependents=3))
        known = frozenset({"employment_income"})
        assert features(a, known) == features(b, known)
        assert handcrafted_scorer(a, known) == handcrafted_scorer(b, known)

    def test_nothing_reads_the_oracle(self):
        """
        features() takes the household and the known set. It never indexes
        case["states"], which is the verdict being predicted.
        """
        import inspect

        from abstain import scorer
        src = inspect.getsource(scorer.features)
        assert "states" not in src

    def test_unknown_income_scores_at_the_floor(self):
        """
        Sweeping an unknown income across its range flips eligibility on
        essentially every household, so the case is open and the score is
        zero.

        An arbitrary floor of 0.05 sat here first and produced an inversion:
        a case whose income was known to sit inside the ambiguous band scored
        below one where income was unknown entirely. Both are undecidable.
        """
        assert handcrafted_scorer(CASE, frozenset({"age"})) == 0.0

    def test_knowing_income_far_from_the_boundary_beats_not_knowing_it(self):
        far = dict(CASE, household=dict(CASE["household"],
                                        employment_income=60_000))
        assert handcrafted_scorer(far, frozenset({"employment_income"})) > \
               handcrafted_scorer(far, frozenset({"age"}))


class TestHandcrafted:

    def test_distance_from_the_boundary_raises_the_score(self):
        near = dict(CASE, household=dict(CASE["household"],
                                         employment_income=24_000))
        far = dict(CASE, household=dict(CASE["household"],
                                        employment_income=60_000))
        k = frozenset({"employment_income", "dependents"})
        assert handcrafted_scorer(far, k) > handcrafted_scorer(near, k)

    def test_knowing_more_raises_the_score(self):
        few = frozenset({"employment_income"})
        many = frozenset({"employment_income", "dependents", "state_name"})
        assert handcrafted_scorer(CASE, many) > handcrafted_scorer(CASE, few)

    def test_it_stays_in_range(self):
        for k in (frozenset(), frozenset({"employment_income"}),
                  frozenset({"employment_income", "dependents", "age",
                             "state_name"})):
            assert 0.0 <= handcrafted_scorer(CASE, k) <= 1.0


class TestAUC:

    def test_a_perfect_ordering_is_one(self):
        assert auc([(0.9, True), (0.8, True), (0.2, False)]) == 1.0

    def test_a_reversed_ordering_is_zero(self):
        assert auc([(0.1, True), (0.9, False)]) == 0.0

    def test_a_constant_score_is_a_half(self):
        assert auc([(0.5, True), (0.5, False)]) == 0.5

    def test_it_measures_order_not_calibration(self):
        """
        The rule only ever uses the score's order, so a monotone transform of
        the score must not change the measure. Reporting log-loss would be
        measuring something the method does not use.
        """
        base = [(0.9, True), (0.4, True), (0.1, False)]
        squashed = [(s / 10, d) for s, d in base]
        assert auc(base) == auc(squashed)


class TestFitted:

    @pytest.fixture(scope="class")
    def samples(self):
        p = ROOT / "evidence" / "dev.json"
        if not p.exists():
            pytest.skip("dev set not built")
        import itertools

        from abstain.scorer import FIELDS
        dev = json.loads(p.read_text())[:20]
        return [(c, frozenset(k),
                 c["states"]["|".join(sorted(k))]["label"] == "determinable")
                for c in dev for r in range(len(FIELDS) + 1)
                for k in itertools.combinations(FIELDS, r)]

    def test_it_beats_the_constant_scorer(self, samples):
        f = FittedScorer().fit(samples, epochs=120)
        pairs = [(f(c, k), d) for c, k, d in samples]
        const = [(constant_scorer(c, k), d) for c, k, d in samples]
        assert auc(pairs) > auc(const) + 0.2

    def test_it_records_what_it_was_trained_on(self, samples):
        f = FittedScorer().fit(samples, epochs=50)
        assert f.trained_on == len(samples)

    def test_it_stays_in_range(self, samples):
        f = FittedScorer().fit(samples, epochs=50)
        assert all(0.0 <= f(c, k) <= 1.0 for c, k, _ in samples[:50])
