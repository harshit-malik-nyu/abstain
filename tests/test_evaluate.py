"""
Tests for the evaluation.

The central one pins a bug that made every comparison meaningless: a rule
that decides to answer does not get to abstain, and conflating the two made
"answer immediately" score 0% unsafe.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abstain.evaluate import (
    answer_immediately, ask_everything, evaluate, ever_decidable, oracle,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dev():
    p = ROOT / "evidence" / "dev.json"
    if not p.exists():
        pytest.skip("dev set not built")
    return json.loads(p.read_text())


class TestCommittingIsNotAbstaining:

    def test_answering_immediately_is_maximally_unsafe(self, dev):
        """
        THE BUG. run_case read the verdict off the oracle when it answered,
        and at an undecidable state the oracle says "cannot_determine" — so a
        rule that chose to commit was scored as having abstained. Answer-
        immediately came out at 0% unsafe, the exact opposite of what it is.
        """
        r = answer_immediately(dev)
        assert r.unsafe_rate > 0.7
        assert r.questions_per_case == 0.0

    def test_a_committed_guess_is_unsafe_whichever_way_it_guesses(self):
        """
        Scoring the guess as right half the time would hide the failure. The
        commitment is the failure.
        """
        case = {"id": 0, "household": {"employment_income": 20000,
                                       "dependents": 1, "age": 35,
                                       "state_name": "NY"},
                "states": {"employment_income": {"label": "underdetermined",
                                                 "truth": "cannot_determine"}}}
        r = evaluate([case], lambda c, k: 1.0, 0.0, "commit", budget=0)
        assert r.unsafe == 1
        assert r.abstained == 0

    def test_running_out_of_budget_is_an_abstention(self, dev):
        r = ask_everything(dev)
        assert r.unsafe_rate == 0.0
        assert r.abstained == r.n


class TestReferencePolicies:

    def test_the_three_fail_differently(self, dev):
        """
        Each is perfect on one axis and worthless on another. A method has to
        beat all three at once, which is why all three columns are reported.
        """
        a, e, o = answer_immediately(dev), ask_everything(dev), oracle(dev)
        assert a.unsafe_rate > 0.7 and a.questions_per_case == 0.0
        assert e.unsafe_rate == 0.0 and e.coverage == 0.0
        assert o.unsafe_rate == 0.0 and o.coverage == 1.0

    def test_the_oracle_costs_fewer_questions_than_asking_everything(self, dev):
        assert oracle(dev).questions_per_case < ask_everything(dev).questions_per_case

    def test_coverage_is_over_decidable_cases_only(self, dev):
        """
        A case that is undecidable however many questions are asked cannot be
        resolved by anyone, and counting it against a policy would penalise
        the policy for the benchmark.
        """
        o = oracle(dev)
        assert o.decidable <= o.n
        assert o.coverage == 1.0

    def test_every_summary_carries_all_three_axes(self, dev):
        d = oracle(dev).as_dict()
        for k in ("unsafe_rate", "coverage", "questions_per_case"):
            assert k in d


class TestEverDecidable:

    def test_a_case_with_no_decidable_state_is_excluded_from_coverage(self):
        case = {"id": 1, "household": {}, "states": {
            "a": {"label": "underdetermined", "truth": "cannot_determine"}}}
        assert not ever_decidable(case)

    def test_a_case_with_one_is_counted(self):
        case = {"id": 1, "household": {}, "states": {
            "a": {"label": "underdetermined", "truth": "cannot_determine"},
            "b": {"label": "determinable", "truth": "eligible"}}}
        assert ever_decidable(case)
