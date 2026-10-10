"""
Every evidence file is accounted for, and every live one is checkable.

Why this file exists
--------------------
Two of this repository's four numbered claims rested on evidence files that
**no script produced and no test read**. One of them carried the vacuous zero
that the repository documents as its own third bug — zero violations over
zero certified trials — in a file added seven commits before the fix. It
survived sixteen rounds because nothing in the pipeline looked at it.

That was a structural gap rather than one mistake: with forty-one JSON files
accumulated over sixteen rounds, nothing distinguished the ones backing
published claims from the leftovers. So `evidence/MANIFEST.md` classifies
every file and this enforces the classification:

- every JSON in `evidence/` is listed somewhere in the manifest
- every file the manifest calls **live** has a producing script
- every live file is read by at least one test
- every **pre-correction** file still lacks the conditioned metric, because
  regenerating one would erase the record of what was wrong

The third assertion is the one that would have caught the original defect.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "MANIFEST.md"


def manifest_text() -> str:
    if not MANIFEST.exists():
        pytest.skip("evidence/MANIFEST.md is not in this checkout")
    return MANIFEST.read_text()


def section(name: str) -> str:
    """One `##` section of the manifest, by the start of its heading."""
    lines = manifest_text().splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("## ") and name in ln)
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end])


def listed_files(text: str) -> set[str]:
    """
    The files a section CLASSIFIES — the first cell of each table row.

    Not every backticked name in the section: the superseded table says
    things like "superseded by `fitted_conditional.json`", and the first
    version of this helper counted that as a listing, which put a live file
    in the superseded set and failed four assertions at once. The column a
    row is about is its first one.
    """
    out: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        first = line.split("|")[1]
        out |= set(re.findall(r"`([A-Za-z0-9_.\-]+\.json)`", first))
    return out


def all_mentioned(text: str) -> set[str]:
    """Every backticked name anywhere, for the "is it listed at all" check."""
    return set(re.findall(r"`([A-Za-z0-9_.\-]+\.json)`", text))


def evidence_jsons() -> set[str]:
    return {p.name for p in (ROOT / "evidence").glob("*.json")}


def walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def test_every_evidence_file_is_listed():
    """
    An unlisted file is one a reader cannot classify, which is how a
    superseded result gets mistaken for a current one.
    """
    text = manifest_text()
    listed = all_mentioned(text)
    # Wildcards cover the digest files and the two split pairs.
    unlisted = {n for n in evidence_jsons() if n not in listed}
    # `*.meta.json` and `*.sha256` are covered by glob entries in the table.
    unlisted = {n for n in unlisted
                if not any(re.fullmatch(pat.replace("*", ".*"), n)
                           for pat in re.findall(r"`([^`]*\*[^`]*)`", text))}
    assert not unlisted, sorted(unlisted)


def test_unregenerable_files_are_declared_and_read():
    """
    The third category: backs a claim, has no script, and says why.

    Added when the figure audit found `fitted_secondary.json` backing the
    excluded-scorer table from the superseded table. It is a holdout run, so
    regenerating it would open the holdout a second time — which is not a
    thing to do for a provenance tidy-up. The honest handling is a declared
    exception with a reading test, not a silent one.
    """
    text = manifest_text()
    try:
        sect = section("Live, and not regenerable")
    except StopIteration:
        pytest.skip("no unregenerable section in this manifest")

    declared = listed_files(sect)
    assert declared, "the section exists but classifies nothing"
    assert "holdout" in sect, \
        "the reason has to be in the table, not implied"

    tests = {p.name: p.read_text() for p in (ROOT / "tests").glob("*.py")}
    for name in sorted(declared):
        stem = name[:-5]
        assert any(stem in t for t in tests.values()), \
            (name, "an unregenerable file still needs a reading test")
        # And it must NOT also be listed as live, or the exception is
        # being claimed twice.
        assert name not in listed_files(section("Live —")), name
    del text


def test_every_live_file_has_a_producing_script():
    """
    The first half of the defect: a file nothing writes cannot be
    regenerated, so an error in it is permanent.
    """
    live = listed_files(section("Live"))
    assert len(live) > 15, sorted(live)

    sources = {p.name: p.read_text()
               for p in (ROOT / "scripts").glob("*.py")}
    sources |= {p.name: p.read_text()
                for p in (ROOT / ".github" / "workflows").glob("*.yml")}

    orphans = []
    for name in sorted(live):
        stem = name[:-5]
        # Scripts build some names from a variable, so match the stem's
        # prefix too -- `round4_{args.set}.json` writes `round4_dev.json`.
        root = stem.split("_")[0]
        # Some scripts derive the name rather than spelling it:
        # `run_round4.py` writes f"round4_{args.set}.json", and
        # `build_cases.py` writes the meta file via
        # `Path(out).with_suffix(".meta.json")`. Matching the stem alone
        # would report both as orphaned, which is a false alarm in the
        # direction that gets a guard switched off.
        derived = stem.endswith(".meta") and any(
            'with_suffix(".meta.json")' in t for t in sources.values())
        if not (derived or any(stem in t or (root in t and "evidence" in t)
                               for t in sources.values())):
            orphans.append(name)
    assert not orphans, (
        "listed as live but no script writes them", orphans)


def test_every_live_file_is_read_by_a_test():
    """
    The second half, and the assertion that would have caught the original
    defect. `unit_comparison.json` and `leakage.json` backed a numbered
    claim and no test read either, so nothing checked the figures in it.
    """
    live = listed_files(section("Live"))
    tests = {p.name: p.read_text() for p in (ROOT / "tests").glob("*.py")}

    unread = []
    for name in sorted(live):
        stem = name[:-5]
        if not any(stem in t for t in tests.values()):
            unread.append(name)
    assert not unread, (
        "listed as live but no test reads them", unread)


def test_pre_correction_files_stay_pre_correction():
    """
    They are kept to show what a published figure was before it was
    corrected. Regenerating one with the current metric would erase that,
    and the file would silently stop being evidence of anything.
    """
    text = section("Pre-correction")
    rows = [ln for ln in text.splitlines()
            if ln.startswith("|") and not ln.startswith("|---")]
    marked = set()
    for line in rows:
        cells = line.split("|")
        if "pre-fix metric" in line:
            marked |= set(re.findall(r"`([A-Za-z0-9_.\-]+\.json)`", cells[1]))
    assert marked, (
        "no pre-correction row is marked as carrying the pre-fix metric; "
        "the manifest must say which, since only those are checked here")

    for name in sorted(marked):
        p = ROOT / "evidence" / name
        if not p.exists():
            continue
        dicts = list(walk(json.loads(p.read_text())))
        assert not any("violation_rate_when_feasible" in d for d in dicts), \
            f"{name} has been regenerated and is no longer the record"


def test_superseded_files_are_referenced_by_nothing():
    """
    The manifest's claim about them, asserted rather than trusted.

    If one of these starts backing a write-up figure it has to move to the
    live table and acquire a script and a test, because it carries the
    pre-fix metric and a table built from it can hold a vacuous zero.
    """
    # Source docstrings count. Leaving them out is how
    # `validation_dev.json` sat in the superseded table while two module
    # docstrings quoted its 35.8%.
    looked_at = [ROOT / "README.md"]
    looked_at += sorted((ROOT / "docs").glob("*.md"))
    looked_at += sorted((ROOT / "src" / "abstain").glob("*.py"))
    corpus = "\n".join(p.read_text() for p in looked_at)

    for name in sorted(listed_files(section("Superseded"))):
        stem = name[:-5]
        # theory.md names search_correction's figures in prose; the manifest
        # says so, so the file itself must still not be cited as a source.
        assert f"evidence/{name}" not in corpus, (
            f"{name} is cited as a source but is listed as superseded")
        assert f"`{stem}`" not in corpus or stem == "search_correction", name


def test_the_manifest_explains_the_metric_that_changed_meaning():
    """
    The manifest is only useful if it says *why* the vintage matters. A
    reader who does not know that `violation_rate` pools over declined
    trials cannot tell that a 0.0% in a pre-fix file may be vacuous.
    """
    t = " ".join(manifest_text().split())
    assert "violation_rate_when_feasible" in t
    assert "vacuous zero" in t
    assert "commit 13" in t, \
        "the manifest should date the fix so a file's vintage is checkable"
