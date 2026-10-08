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
