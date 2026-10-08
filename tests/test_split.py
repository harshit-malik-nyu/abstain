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


def digest_of(name: str) -> str:
    return hashlib.sha256((ROOT / "evidence" / f"{name}.json")
                          .read_bytes()).hexdigest()


class TestTheSplitIsIntact:

    @pytest.mark.parametrize("half", ["dev", "holdout"])
    def test_the_committed_digest_still_matches(self, half):
        """
        If either half is edited, this fails. That is the whole mechanism:
        the holdout's value is that it has not moved, and a silent edit would
        destroy it without any other test noticing.
        """
        recorded = (ROOT / "evidence" / f"{half}.sha256").read_text().strip()
        assert digest_of(half) == recorded

    def test_the_halves_do_not_overlap(self):
        dev = {c["id"] for c in json.loads((ROOT / "evidence" / "dev.json").read_text())}
        hold = {c["id"] for c in json.loads((ROOT / "evidence" / "holdout.json").read_text())}
        assert dev and hold
        assert not (dev & hold)

    def test_together_they_are_the_whole_benchmark(self):
        table = json.loads((ROOT / "evidence" / "oracle_table.json").read_text())
        dev = json.loads((ROOT / "evidence" / "dev.json").read_text())
        hold = json.loads((ROOT / "evidence" / "holdout.json").read_text())
        assert len(dev) + len(hold) == len(table)

    def test_it_regenerates_from_the_committed_seed(self):
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
        sys.path.insert(0, str(ROOT / "scripts"))
        from split import hardness

        for half in ("dev", "holdout"):
            rows = json.loads((ROOT / "evidence" / f"{half}.json").read_text())
            assert len({hardness(c) for c in rows}) >= 3

    def test_each_half_is_large_enough_to_measure_on(self):
        """
        Seven cases gives a standard error near 19 points on a rate, wider
        than every effect this project tries to detect. That was the reason
        for regenerating rather than splitting what existed.
        """
        for half in ("dev", "holdout"):
            rows = json.loads((ROOT / "evidence" / f"{half}.json").read_text())
            assert len(rows) >= 60, f"{half} has only {len(rows)} cases"
