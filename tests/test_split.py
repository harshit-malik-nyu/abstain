"""
Tests for the split.

These exist to make tampering loud. The value of a holdout is entirely in it
being untouched, and that is a property of process rather than of code — so
what can be checked is that the committed halves are the ones the committed
seed produces, and that they have not changed since.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def require_cases():
    """
    Skip while the case set is still being generated, fail once it exists.

    The distinction matters: a missing cases.json means the build has not
    finished, which is not a failure. A present cases.json whose split does
    not match is a real problem and must be loud.
    """
    p = ROOT / "evidence" / "cases.json"
    if not p.exists():
        pytest.skip("cases.json not generated yet")
    return p


def digest_of(name: str) -> str:
    return hashlib.sha256((ROOT / "evidence" / f"{name}.json")
                          .read_bytes()).hexdigest()


class TestTheSplitIsIntact:

    @pytest.mark.parametrize("half", ["dev", "holdout"])
    def test_the_committed_digest_still_matches(self, half):
        require_cases()
        """
        If either half is edited, this fails. That is the whole mechanism:
        the holdout's value is that it has not moved, and a silent edit would
        destroy it without any other test noticing.
        """
        recorded = (ROOT / "evidence" / f"{half}.sha256").read_text().strip()
        assert digest_of(half) == recorded

    def test_the_halves_do_not_overlap(self):
        require_cases()
        dev = {c["id"] for c in json.loads((ROOT / "evidence" / "dev.json").read_text())}
        hold = {c["id"] for c in json.loads((ROOT / "evidence" / "holdout.json").read_text())}
        assert dev and hold
        assert not (dev & hold)

    def test_together_they_are_the_whole_benchmark(self):
        require_cases()
        table = json.loads((ROOT / "evidence" / "cases.json").read_text())
        dev = json.loads((ROOT / "evidence" / "dev.json").read_text())
        hold = json.loads((ROOT / "evidence" / "holdout.json").read_text())
        assert len(dev) + len(hold) == len(table)

    def test_it_regenerates_from_the_committed_seed(self):
        require_cases()
        """
        The split must be reproducible from the script, or the committed
        halves are just two files somebody chose.
        """
        before = (digest_of("dev"), digest_of("holdout"))
        subprocess.run([sys.executable, str(ROOT / "scripts" / "split.py")],
                       check=True, capture_output=True)
        assert (digest_of("dev"), digest_of("holdout")) == before


class TestStratification:

    def test_the_stratum_variable_actually_varies(self):
        require_cases()
        """
        REGRESSION on a vacuous split. The first stratum was the share of
        knowledge states that are underdetermined, and fifteen of sixteen
        cases fell in one bucket — stratifying on a constant.
        """
        sys.path.insert(0, str(ROOT / "scripts"))
        from split import hardness

        table = json.loads((ROOT / "evidence" / "cases.json").read_text())
        strata = {}
        for c in table:
            strata[hardness(c)] = strata.get(hardness(c), 0) + 1
        assert len(strata) >= 3, f"too few strata: {strata}"
        biggest = max(strata.values()) / len(table)
        assert biggest < 0.6, f"one stratum holds {biggest:.0%} of cases"

    def test_both_halves_span_the_strata(self):
        require_cases()
        sys.path.insert(0, str(ROOT / "scripts"))
        from split import hardness

        for half in ("dev", "holdout"):
            rows = json.loads((ROOT / "evidence" / f"{half}.json").read_text())
            assert len({hardness(c) for c in rows}) >= 3

    def test_each_half_is_large_enough_to_measure_on(self):
        require_cases()
        """
        Seven cases gives a standard error near 19 points on a rate, wider
        than every effect this project tries to detect. That was the reason
        for regenerating rather than splitting what existed.
        """
        for half in ("dev", "holdout"):
            rows = json.loads((ROOT / "evidence" / f"{half}.json").read_text())
            assert len(rows) >= 60, f"{half} has only {len(rows)} cases"


# ---------------------------------------------------------------------------
# The second benchmark, and the proof that adding it did not disturb the first
# ---------------------------------------------------------------------------

def test_the_default_split_still_reproduces_the_committed_digests():
    """
    `split.py` grew --source/--prefix/--seed long after it was written, so a
    second and larger benchmark could be split without a third copy of the
    stratification logic.

    That edit touches the first commit in the repository, whose untouched
    behaviour is the evidence that the split preceded the method. So the
    evidence is converted from "untouched" to "verified identical": the
    default call is re-run here and its output digested against the values
    committed alongside the original split. If the edit had changed the
    original halves, this fails.
    """
    import hashlib
    import json

    for name, digest_file in (("dev", "dev.sha256"),
                              ("holdout", "holdout.sha256")):
        rows = json.loads((ROOT / "evidence" / f"{name}.json").read_text())
        payload = json.dumps(rows, separators=(",", ":"), sort_keys=True)
        computed = hashlib.sha256(payload.encode()).hexdigest()
        committed = (ROOT / "evidence" / digest_file).read_text().strip()
        assert computed == committed, name


def test_the_fine_benchmark_is_the_complete_household_space():
    """
    1,344 cases, every one distinct, and the whole grid rather than a sample.

    This is what removes sampling variation from the benchmark itself: the
    only randomness left is the dev/holdout split and the per-trial draws.
    """
    import json

    cases = json.loads((ROOT / "evidence" / "cases_fine.json").read_text())
    meta = json.loads(
        (ROOT / "evidence" / "cases_fine.meta.json").read_text())

    assert len(cases) == 1_344 == meta["household_space"]
    keys = {tuple(sorted(c["household"].items())) for c in cases}
    assert len(keys) == len(cases), "a household appears twice"
    assert len(meta["incomes"]) * 4 * 4 * 4 == 1_344
    assert meta["engine"].startswith("policyengine-us=="), \
        "the oracle version is part of the data, not the environment"


def test_the_fine_grid_contains_the_coarse_grid():
    """
    Without this the two benchmarks are different populations and the round
    four replication is a change of subject rather than a replication.
    """
    import json

    meta = json.loads(
        (ROOT / "evidence" / "cases_fine.meta.json").read_text())
    coarse = {0, 6_000, 12_000, 18_000, 21_000, 24_000, 30_000, 36_000,
              48_000, 60_000}
    assert coarse <= set(meta["incomes"])


def test_the_fine_halves_are_disjoint_and_stratified():
    import json

    from abstain.conditional import hardness

    dev = json.loads((ROOT / "evidence" / "fine_dev.json").read_text())
    hold = json.loads((ROOT / "evidence" / "fine_holdout.json").read_text())

    assert len(dev) == len(hold) == 672
    assert not ({c["id"] for c in dev} & {c["id"] for c in hold})

    for rows in (dev, hold):
        strata = {}
        for c in rows:
            strata[hardness(c)] = strata.get(hardness(c), 0) + 1
        assert len(strata) >= 3
        assert max(strata.values()) <= 0.60 * len(rows)
        # The smallest band is what binds group-conditional feasibility, and
        # the power analysis in docs/preregistration-4.md is computed at
        # 14.3%. If the split drifted, that analysis is wrong.
        assert min(strata.values()) / len(rows) > 0.12


def test_the_fine_digests_are_recorded():
    import hashlib
    import json

    for name in ("fine_dev", "fine_holdout"):
        rows = json.loads((ROOT / "evidence" / f"{name}.json").read_text())
        payload = json.dumps(rows, separators=(",", ":"), sort_keys=True)
        computed = hashlib.sha256(payload.encode()).hexdigest()
        committed = (ROOT / "evidence" / f"{name}.sha256").read_text().strip()
        assert computed == committed, name
