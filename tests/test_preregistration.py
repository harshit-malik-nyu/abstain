"""
The pre-registration must stay honest.

A pre-registration that can be edited after the result is not one. These
assert it contains falsifiable predictions and names the outcome that would
sink the project, so a later softening is visible in a diff.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prereg() -> str:
    return (ROOT / "docs" / "preregistration.md").read_text()


class TestItCommitsToSomething:

    def test_the_primary_prediction_is_numeric(self):
        t = prereg()
        assert "at or below\n0.05" in t or "at or below **0.05**" in t

    def test_it_names_what_would_falsify_the_project(self):
        t = prereg()
        assert "What would falsify the project" in t
        assert "P1 fails" in t

    def test_it_distinguishes_falsifying_from_merely_disappointing(self):
        """
        A pre-registration that treats every miss as fatal is not a plan, it
        is a hedge. Coverage missing its interval while the guarantee holds
        is a reason to improve the scorer, not to doubt the rule.
        """
        t = prereg()
        assert "What would not falsify it" in t
        assert "reason to improve\nthe scorer" in t or \
               "reason to improve the scorer" in " ".join(t.split())

    def test_the_frozen_method_is_specified(self):
        t = prereg()
        for item in ("handcrafted_scorer", "calibrate_on_trajectories",
                     "101 points", "budget"):
            assert item.lower() in t.lower(), item

    def test_the_analysis_plan_forbids_tuning(self):
        t = prereg()
        assert "No tuning after opening" in t
        assert "reported bad" in t


class TestItPrecededTheHoldout:

    def test_no_committed_code_reads_the_holdout_yet(self):
        """
        The discipline is the ordering. Until the holdout script exists, no
        tracked file should reference holdout.json except the split that
        wrote it and the tests that check its digest.
        """
        out = subprocess.run(
            ["git", "grep", "-l", "holdout.json"],
            cwd=ROOT, capture_output=True, text=True).stdout.split()
        # Files that may legitimately name the holdout before it is opened:
        # the script that wrote it, the tests that check its digest, and the
        # documents that describe the discipline. Anything else reading it is
        # the discipline being broken.
        allowed = {"scripts/split.py", "tests/test_split.py",
                   "tests/test_preregistration.py", "README.md",
                   "docs/preregistration.md"}
        unexpected = {f for f in out if not f.endswith(".pyc")} - allowed
        assert not unexpected, f"these read the holdout early: {unexpected}"


class TestTheResultIsReportedAsPredicted:
    """
    The pre-registration is only worth something if the scoring is honest.
    These assert the miss is recorded as a miss rather than softened.
    """

    @staticmethod
    def _check():
        import json
        p = ROOT / "evidence" / "prediction_check.json"
        if not p.exists():
            import pytest
            pytest.skip("holdout not opened")
        return json.loads(p.read_text())

    def test_the_primary_prediction_held(self):
        assert self._check()["P1"]

    def test_the_miss_is_recorded_as_a_miss(self):
        """
        P2 came in at 5.3% against a 5% target. It is 0.19 standard errors
        over and it is still a miss. Recording it as held would be the
        easiest possible way to make a pre-registration worthless.
        """
        c = self._check()
        assert c["P2"] is False
        assert 0 < c["P2_excess_pp"] < 1
        assert abs(c["P2_standard_errors"]) < 1

    def test_the_readme_calls_it_a_miss(self):
        t = (ROOT / "README.md").read_text()
        assert "missed" in t.lower()
        assert "still a miss" in t

    def test_coverage_did_not_degrade_from_dev_to_holdout(self):
        """
        A method tuned against its development set degrades on unseen data.
        This is the clearest available evidence that the holdout stayed shut.
        """
        c = self._check()
        assert c["holdout_coverage_at_0.10"] >= c["dev_coverage_at_0.10"]

    def test_the_shape_predictions_held(self):
        c = self._check()
        assert c["P7"] and c["P8"]
