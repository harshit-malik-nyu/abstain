"""
The pre-registration must stay honest.

A pre-registration that can be edited after the result is not one. These
assert it contains falsifiable predictions and names the outcome that would
sink the project, so a later softening is visible in a diff.
"""

from __future__ import annotations

import subprocess

import pytest
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

    @staticmethod
    def _readers(pattern: str) -> set[str]:
        """
        Files that name the holdout, restricted to things that could read it.

        `evidence/` is excluded, and that is a tightening rather than a
        loosening: those files are run OUTPUT. A log prints the name of the
        set it was given, so the guard was firing on the very record the run
        produced — matching a string in a result rather than a read in code.
        Allow-listing each log one by one would have grown an exception list
        that eventually swallowed a real reader.

        What the guard is actually about is code paths, so it looks at those.
        """
        out = subprocess.run(
            ["git", "grep", "-l", pattern],
            cwd=ROOT, capture_output=True, text=True).stdout.split()
        return {f for f in out
                if not f.endswith(".pyc")
                and not f.startswith("evidence/")}

    def test_only_the_opening_script_and_the_split_touch_the_holdout(self):
        """
        Opening it once is the plan. A second analysis path reading the
        holdout would be a second look, whatever it was called.

        The pattern is the **exact** path, not any string containing
        "holdout.json". It used to be the loose version, and when a second
        benchmark arrived with its own `fine_holdout.json` the guard fired on
        a document that never touches the original — it could not tell the two
        apart. Loosening it to pass would have left both holdouts unguarded,
        so it is split into one guard per benchmark instead.
        """
        allowed = {"scripts/split.py", "scripts/open_holdout.py",
                   "tests/test_split.py", "tests/test_preregistration.py",
                   "README.md", "docs/preregistration.md", "docs/theory.md",
                   # Round four declares that it does not read this file.
                   # Mentioning it in order to say so is not reading it.
                   "docs/preregistration-4.md",
                   # And the build workflow names it only to assert it has
                   # not changed. A guard is not a reader: that step exists
                   # because a rebuild under a newer oracle would otherwise
                   # replace these halves silently, which is the failure
                   # this whole class of test is about.
                   ".github/workflows/build.yml"}
        unexpected = self._readers("evidence/holdout.json") - allowed
        assert not unexpected, f"extra readers of the coarse holdout: {unexpected}"

    def test_only_round_four_touches_the_fine_holdout(self):
        """
        The second benchmark's holdout gets the same discipline as the first.

        A new benchmark is a new chance to spend a holdout casually, and the
        guard that protects the original would not have noticed: it matched
        one filename. This one matches the other.
        """
        allowed = {"scripts/split.py", "scripts/run_round4.py",
                   "tests/test_split.py", "tests/test_preregistration.py",
                   "README.md", "docs/preregistration-4.md",
                   # Names the holdout's evidence files only to check that
                   # the interrupted and resumed runs agree. A verifier is
                   # not a reader, same as the build workflow above.
                   "scripts/verify_resumed_run.py",
                   # And the write-up reports the result, which is the
                   # point of having opened it.
                   "docs/results-secondary.md"}
        unexpected = self._readers("fine_holdout") - allowed
        assert not unexpected, f"extra readers of the fine holdout: {unexpected}"

    def test_the_coarse_holdout_is_not_read_by_round_four(self):
        """
        Round four says in its analysis plan that it does not touch the
        original holdout. Asserted rather than trusted.
        """
        for script in ("scripts/run_round4.py", "scripts/run_secondary.py",
                       "scripts/rerun_corruption.py"):
            path = ROOT / script
            if not path.exists():
                continue
            body = path.read_text()
            assert "evidence/holdout.json" not in body, script
            assert '"holdout"' not in body or "fine_" in body, script


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

        The pinned sentence changed once, and the reason is worth recording.
        This test originally required the phrase "AUC is the wrong summary for
        choosing between scorers here", and a README rewrite dropped it — not
        by softening the claim but by generalising it, once two further
        results said the same thing about AUC from different directions. The
        test caught the loss, which is what it is for.

        So it now pins the numbers and the broader claim rather than one
        sentence. Pinning prose exactly makes a test fire on every rewording;
        pinning the figures makes it fire only when the finding itself goes
        missing.
        """
        t = " ".join((ROOT / "README.md").read_text().split())

        # The evidence: nearly identical ordering, wildly different coverage.
        assert "0.9644" in t and "0.9631" in t
        assert "97.7%" in t and "74.8%" in t

        # And the conclusion drawn from it, which must still be stated.
        assert "AUC cannot see what this" in t, \
            "the AUC defect must be stated as a conclusion, not left to the " \
            "reader to infer from two numbers"

    def test_all_three_auc_results_are_reported_together(self):
        """
        Three independent results now say AUC cannot see what this method
        does, and they are only persuasive together.

        The excluded scorer winning at an identical AUC; a strictly monotone
        corruption leaving AUC unchanged to the floating-point bit; and every
        income band above 0.93 while one absorbs 4.1x its share of the error
        budget. Any one is a curiosity. The three are a claim about the
        metric, so the write-up has to carry the count.
        """
        t = " ".join((ROOT / "README.md").read_text().split())
        assert "third independent result" in t
        assert "0.9976" in t, "the per-band AUC table is the third result"
        assert "4.1" in t, "the concentration figure is what it is set against"


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


class TestTheBenchmarkCannotBeSilentlyReplaced:
    """
    The rebuild workflow is a path by which the holdout could change without
    anyone deciding to change it, and it took four rounds to notice.
    """

    def test_the_oracle_version_is_pinned_in_ci(self):
        """
        Determinability is defined by what PolicyEngine says, which makes the
        version part of the data rather than part of the environment.

        The workflow installed the latest release, so a rerun months later
        would build a different benchmark under the same filename — and the
        next step re-splits. Unpinned, that silently replaces the halves the
        primary result rests on.
        """
        import json
        wf = (ROOT / ".github" / "workflows" / "build.yml").read_text()
        meta = json.loads(
            (ROOT / "evidence" / "cases_fine.meta.json").read_text())
        pinned = meta["engine"]

        assert "pip install policyengine-us\n" not in wf, \
            "the oracle must not be installed unpinned"
        assert pinned in wf, \
            f"CI must pin the version the data records: {pinned}"

    def test_a_rebuild_that_changes_the_split_fails_the_build(self):
        wf = (ROOT / ".github" / "workflows" / "build.yml").read_text()
        assert "git diff --exit-code" in wf
        assert "evidence/dev.sha256" in wf and "evidence/holdout.sha256" in wf

    def test_the_recorded_oracle_version_is_a_real_pin(self):
        import json
        import re
        meta = json.loads(
            (ROOT / "evidence" / "cases_fine.meta.json").read_text())
        assert re.fullmatch(r"policyengine-us==\d+\.\d+\.\d+",
                            meta["engine"]), meta["engine"]


class TestTheHoldoutWasOpenedOnceDespiteTheInterruption:
    """
    The confirmatory run was killed partway through and relaunched.

    That is indistinguishable from a second look unless it is checked, and
    "it was the same seed" is an assertion rather than a check. These make it
    one.
    """

    PARTIAL = "evidence/round4-holdout-partial-interrupted.txt"
    COMPLETE = "evidence/round4-holdout-run.txt"

    def _rows(self, name: str) -> list[str]:
        import re
        path = ROOT / name
        out = []
        for line in path.read_text().splitlines():
            s = " ".join(line.split())
            if not s or not re.search(r"\d", s):
                continue
            if s.startswith("---") or "----" in s:
                continue
            if s.startswith("wrote evidence/"):
                continue
            out.append(s)
        return out

    def test_the_interrupted_log_was_committed_before_the_relaunch(self):
        """
        Otherwise it could have been edited afterwards to agree, and the
        whole check would be circular.
        """
        import subprocess
        if not (ROOT / self.PARTIAL).exists():
            pytest.skip("no interrupted run in this checkout")

        def added(path: str) -> int:
            out = subprocess.run(
                ["git", "log", "--diff-filter=A", "--format=%ct", "--", path],
                cwd=ROOT, capture_output=True, text=True).stdout.split()
            return int(out[-1]) if out else 0

        partial_at = added(self.PARTIAL)
        assert partial_at, "the interrupted log must be committed"

        complete_at = added(self.COMPLETE)
        if complete_at:
            assert partial_at < complete_at, (
                "the interrupted log has to predate the completed one, or it "
                "could have been written to match")

    def test_the_resumed_run_reproduces_every_seen_row(self):
        """
        Character for character. A single number moving means two different
        experiments, and the result should be discarded rather than explained.
        """
        if not (ROOT / self.PARTIAL).exists() or \
                not (ROOT / self.COMPLETE).exists():
            pytest.skip("the resumed run has not completed in this checkout")

        before, after = self._rows(self.PARTIAL), self._rows(self.COMPLETE)
        assert before, "the interrupted log carried no numbers"
        missing = [r for r in before if r not in after]
        assert not missing, (
            "the two runs disagree, so the holdout was opened twice: "
            f"{missing[:3]}")

    def test_the_script_was_not_modified_between_the_two_runs(self):
        """
        A resumed run is the same draw only if the code is the same code.
        """
        import subprocess
        if not (ROOT / self.PARTIAL).exists():
            pytest.skip("no interrupted run in this checkout")

        last_touched = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--",
             "scripts/run_round4.py"],
            cwd=ROOT, capture_output=True, text=True).stdout.strip()
        partial_added = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%ct", "--",
             self.PARTIAL],
            cwd=ROOT, capture_output=True, text=True).stdout.split()
        assert last_touched and partial_added
        assert int(last_touched) < int(partial_added[-1]), (
            "run_round4.py changed after the interrupted run was recorded; "
            "the relaunch is then a different experiment")
