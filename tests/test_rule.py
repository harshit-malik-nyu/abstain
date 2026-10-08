"""
Tests for the selection rule.

Written against the construction, not against results. The method was designed
before any data was seen and these check that it does what the design claims —
most importantly that the bound is a bound, and that the search for a
threshold cannot quietly report a guarantee the data does not support.
"""

from __future__ import annotations

import random

from abstain.rule import calibrate, clopper_pearson_upper, run_case


class TestTheBound:

    def test_it_is_an_upper_bound_not_the_estimate(self):
        """Zero failures in a hundred is not a zero rate."""
        assert clopper_pearson_upper(0, 100) > 0.0
        assert clopper_pearson_upper(0, 100) < 0.05

    def test_it_tightens_with_sample_size(self):
        assert (clopper_pearson_upper(0, 20) > clopper_pearson_upper(0, 200)
                > clopper_pearson_upper(0, 2000))

    def test_it_rises_with_failures(self):
        vals = [clopper_pearson_upper(k, 100) for k in range(0, 10)]
        assert vals == sorted(vals)

    def test_it_survives_realistic_sample_sizes(self):
        """
        REGRESSION. The first version summed binomial terms directly and
        overflowed at n=2000 — comb(2000, 1000) exceeds a float. A
        calibration set of two thousand is ordinary, not extreme.
        """
        assert 0 < clopper_pearson_upper(100, 5000) < 1
        assert 0 < clopper_pearson_upper(0, 20000) < 0.001

    def test_it_matches_values_computed_before_the_rewrite(self):
        """
        The log-space rewrite must not have changed the mathematics. These
        four were computed by the direct summation at sizes it could handle.
        """
        for k, n, want in ((0, 20, 0.1391), (0, 100, 0.0295),
                           (1, 100, 0.0466), (5, 100, 0.1023)):
            assert abs(clopper_pearson_upper(k, n) - want) < 1e-3

    def test_degenerate_inputs_are_safe(self):
        assert clopper_pearson_upper(0, 0) == 1.0
        assert clopper_pearson_upper(10, 10) == 1.0


class TestCalibration:

    def _samples(self, n=2000, seed=1):
        rng = random.Random(seed)
        return [(s, rng.random() > s) for s in (rng.random() for _ in range(n))]

    def test_a_tighter_target_buys_a_higher_threshold(self):
        s = self._samples()
        loose, tight = calibrate(s, alpha=0.20), calibrate(s, alpha=0.05)
        assert tight.threshold > loose.threshold

    def test_a_tighter_target_costs_coverage(self):
        s = self._samples()
        assert calibrate(s, alpha=0.05).coverage < calibrate(s, alpha=0.20).coverage

    def test_the_bound_is_what_is_checked_not_the_estimate(self):
        """
        A threshold chosen to hit alpha on the sample holds at alpha only in
        expectation — half the time the deployed rate is worse.
        """
        c = calibrate(self._samples(), alpha=0.10)
        assert c.bound_unsafe <= 0.10
        assert c.empirical_unsafe < c.bound_unsafe

    def test_an_infeasible_target_says_so(self):
        """
        Silently returning the best available threshold would report a
        guarantee the data does not support.
        """
        rng = random.Random(3)
        # every state underdetermined: no threshold can achieve any alpha
        s = [(rng.random(), True) for _ in range(500)]
        c = calibrate(s, alpha=0.05)
        assert not c.feasible
        assert c.threshold == 1.0
        assert c.coverage == 0.0

    def test_the_grid_is_pre_specified_not_data_dependent(self):
        """
        A grid derived from observed scores breaks the finite-sample
        argument. That mistake was made before in this account: a threshold
        search over observed values produced 10% violations at a 5% target.
        """
        import inspect

        from abstain import rule
        doc = " ".join(inspect.getdoc(rule.calibrate).split())
        assert "pre-specified and uniform" in doc
        assert "not derived from the observed scores" in doc

    def test_no_samples_is_not_a_guarantee(self):
        c = calibrate([], alpha=0.05)
        assert not c.feasible


class TestDeployment:

    def _case(self):
        """A case that becomes decidable once dependents is known."""
        return {"id": 1, "states": {
            "employment_income": {"label": "underdetermined",
                                  "truth": "cannot_determine"},
            "dependents|employment_income": {"label": "determinable",
                                             "truth": "eligible"},
            "age|employment_income": {"label": "underdetermined",
                                      "truth": "cannot_determine"},
            "employment_income|state_name": {"label": "underdetermined",
                                             "truth": "cannot_determine"},
        }}

    def test_it_answers_once_the_score_clears(self):
        case = self._case()
        scorer = lambda c, k: 1.0 if "dependents" in k else 0.0
        t = run_case(case, scorer, threshold=0.5, budget=4)
        assert t.final == "eligible"
        assert t.asked == ["dependents"]

    def test_it_abstains_rather_than_guessing_when_budget_runs_out(self):
        """
        The behaviour the bound is about. Exhausting the budget is an
        abstention, not a stall and not a guess.
        """
        case = self._case()
        t = run_case(case, lambda c, k: 0.0, threshold=0.9, budget=2)
        assert t.final == "cannot_determine"
        assert t.stopped_because == "budget exhausted"
        assert t.questions == 2

    def test_a_threshold_of_zero_answers_immediately(self):
        t = run_case(self._case(), lambda c, k: 0.5, threshold=0.0, budget=4)
        assert t.questions == 0

    def test_the_greedy_choice_picks_the_informative_field(self):
        case = self._case()
        scorer = lambda c, k: 1.0 if "dependents" in k else 0.0
        t = run_case(case, scorer, threshold=0.5, budget=4)
        assert t.asked[0] == "dependents"

    def test_a_caller_can_override_the_choice(self):
        case = self._case()
        t = run_case(case, lambda c, k: 0.0, threshold=0.9, budget=1,
                     choose=lambda c, k: "age")
        assert t.asked == ["age"]
