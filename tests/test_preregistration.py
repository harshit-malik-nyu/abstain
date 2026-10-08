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

    def test_the_preregistration_was_committed_before_the_holdout_opened(self):
        """
        The permanent form of the discipline.

        Before the holdout was opened this asserted that no tracked file read
        holdout.json. That check did its job and then correctly fired the
        moment scripts/open_holdout.py appeared — which is legitimate, because
        the holdout is now open.

        What survives opening is the ordering, and git records it. The
        pre-registration must be older than the script that reads the holdout,
        or the predictions were written with the answer in hand.
        """
        def first_commit(path: str) -> str:
            return subprocess.run(
                ["git", "log", "--diff-filter=A", "--format=%ct", "--", path],
                cwd=ROOT, capture_output=True, text=True).stdout.split()[-1]

        prereg_at = int(first_commit("docs/preregistration.md"))
        opened_at = int(first_commit("scripts/open_holdout.py"))
        assert prereg_at < opened_at, (
            "the pre-registration must predate the script that opens the "
            f"holdout: {prereg_at} vs {opened_at}")

    def test_only_the_opening_script_and_the_split_touch_the_holdout(self):
        """
        Opening it once is the plan. A second analysis path reading the
        holdout would be a second look, whatever it was called.
        """
        out = subprocess.run(
            ["git", "grep", "-l", "holdout.json"],
            cwd=ROOT, capture_output=True, text=True).stdout.split()
        allowed = {"scripts/split.py", "scripts/open_holdout.py",
                   "tests/test_split.py", "tests/test_preregistration.py",
                   "README.md", "docs/preregistration.md", "docs/theory.md"}
        unexpected = {f for f in out if not f.endswith(".pyc")} - allowed
        assert not unexpected, f"extra readers of the holdout: {unexpected}"


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


class TestTheSecondaryResultIsReported:
    """
    The pre-registration promised the fitted scorer as a secondary result and
    said it would be reported whether or not it won. It won, against the
    choice made in advance, and that has to survive into the README.
    """

    @staticmethod
    def _rows():
        import json
        p = ROOT / "evidence" / "fitted_secondary.json"
        if not p.exists():
            import pytest
            pytest.skip("secondary result not run")
        return json.loads(p.read_text())

    def test_the_fitted_scorer_beats_the_primary_on_coverage(self):
        rows = self._rows()
        h = next(r for r in rows if r["scorer"] == "handcrafted"
                 and r["alpha"] == 0.10)
        f = next(r for r in rows if r["scorer"] == "fitted"
                 and r["alpha"] == 0.10)
        assert f["mean_coverage"] > h["mean_coverage"] + 0.15

    def test_it_does_so_without_breaking_the_bound(self):
        """
        Winning on coverage by violating would not be winning.
        """
        for r in self._rows():
            if r["scorer"] == "fitted":
                assert r["violation_rate"] <= 0.05

    def test_the_readme_says_the_judgement_was_wrong(self):
        t = (ROOT / "README.md").read_text()
        assert "The judgement was wrong" in t

    def test_the_auc_defect_is_recorded(self):
        """
        A one-point AUC difference producing a twenty-three point coverage
        difference means AUC is the wrong summary for choosing a scorer here.
        That is a defect in the project's own method selection and belongs in
        the write-up rather than in a footnote.
        """
        t = " ".join((ROOT / "README.md").read_text().split())
        assert "AUC is the wrong summary for choosing between scorers here" in t


class TestTheCaseAgainstLeadsWithTheRealLimit:

    def test_it_leads_with_no_model_being_run(self):
        t = (ROOT / "docs" / "against.md").read_text()
        head = t[:t.index("## 2.")]
        assert "There is no model in it" in head
        assert "most serious objection" in head

    def test_it_refuses_the_misleading_comparison(self):
        """
        The companion benchmark's 62.5% and this project's numbers come from
        different cases and different inputs. Tabulating them together would
        be the single most misleading thing available here.
        """
        for doc in ("docs/against.md", "README.md"):
            t = " ".join((ROOT / doc).read_text().split())
            if "62.5%" in t:
                assert "not comparable" in t
