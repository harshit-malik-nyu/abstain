"""
Every percentage in the write-up either matches an evidence number or is
listed here with a reason.

Why this file exists
--------------------
The other coupling tests check the figures a reader would act on — a
deliberately narrow scope, chosen so the suite does not fire on cosmetic
edits. The gap that scope leaves is a figure nobody thought to pin, and two
such figures turned out to be wrong:

- `314 states / 57.0% undetermined`, the middle row of claim 2's mechanism
  table, had no evidence file at all and could not be reproduced. Measured:
  268 / 48.9%.
- Two cells of a band table in `preregistration-5.md` were off by a few
  tenths.

Both were found by extracting every percentage in every document and
checking it against every number in `evidence/`. This makes that audit
permanent. A figure that drifts, or one invented outright, now fails here
even if no targeted test covers it.

What this audit does not catch, measured rather than guessed
------------------------------------------------------------
It is one-sided, and its power is quantifiable. `evidence/` renders to
**4,538 distinct three- and four-place decimals**, so a fabricated
four-place decimal in [0, 1] collides with one by coincidence **17.5% of the
time** — measured, not estimated. Two of the three values tried while
verifying this guard collided, which is how the number came to be measured.

So it catches roughly five figures in six that have **no source anywhere**,
and it says nothing at all about a figure attached to the **wrong** source.
The targeted coupling tests in `test_writeup_matches_evidence.py` do the
second job, table by table, by comparing each published figure to the
specific evidence row it claims to come from. Neither subsumes the other and
the overlap is deliberate.

Quoting "every figure is checked" without that caveat would be the same
overstatement this repository keeps finding in its own prose.

How the allow-list works, and why it is small
---------------------------------------------
A published percentage legitimately has no evidence match in three cases:
it is **computed** from library code rather than measured, it is a
**parameter** of the design rather than a result, or it is **retracted** and
its lack of a source is the point. Each entry below names which, and the
list is short on purpose — a long one would mean the audit had been argued
away rather than satisfied.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

DOCS = ["README.md"] + sorted(
    str(p.relative_to(ROOT)) for p in (ROOT / "docs").glob("*.md"))

# The module docstrings carry substantive claims too, and the first version of
# this audit did not look at them. That gap let `35.8%` — the figure that
# justifies the `refit` parameter in two docstrings — go unaudited, and the
# evidence manifest list it as "referenced by nothing" because the reference
# was in source rather than in the write-up. The figure turned out to be
# sound. It was sound by luck rather than by check.
SOURCES = sorted(str(p.relative_to(ROOT))
                 for p in (ROOT / "src" / "abstain").glob("*.py"))

# Reason codes: computed | parameter | retracted
ALLOWED: dict[str, str] = {
    # Clopper-Pearson floors, from group.reachable_alpha. Computed in closed
    # form from a case count, so no run produces them.
    "34.8%": "computed: reachable_alpha(7)",
    "25.9%": "computed: reachable_alpha(10)",
    "23.8%": "computed: reachable_alpha(11)",
    "13.9%": "computed: reachable_alpha(20)",
    "9.8%": "computed: reachable_alpha(29)",
    "9.81%": "computed: reachable_alpha(29) at two decimals",
    "9.9%": "retracted: the misprinted floor beside 29 cases",
    # The retracted order-flip figures. Their absence from evidence/ is the
    # defect being reported, so pinning them to a file would be wrong.
    "2.78%": "retracted: the ad-hoc flip rate superseded by 3.04%",
    "1.41%": "retracted: the unbiased-sample flip rate in the retraction",
    "4.65%": "retracted: the reachable-state flip rate in the retraction",
    # The superseded middle row, kept visible as what was superseded.
    "57.0%": "retracted: the unreproducible 314-state row",
}

# Bare decimals -- AUCs, Kendall taus, concentrations -- were not audited at
# all until the per-band AUC range turned out to be in no evidence file, from
# the wrong benchmark, and quoted in four documents. Three decimal places is
# the floor: tolerances (0.20, 0.05) and the delta are design parameters, not
# measurements, and matching them would make the audit about parameters.
ALLOWED_DECIMALS: dict[str, str] = {
    # A property of `handcrafted_scorer`, verified against the function.
    "0.9718": "computed: max(handcrafted_scorer) over the benchmark",
    # Round one and round three figures, in pre-registrations that are not
    # edited after the fact. Each is on the 79-case `dev` set and each is
    # labelled as such where it appears.
    "0.9976": "retracted: the dev per-band AUC, superseded by fine_dev",
    "0.9345": "retracted: the dev per-band AUC, superseded by fine_dev",
    "0.9833": "retracted: the dev per-band AUC, superseded by fine_dev",
    "0.9822": "retracted: the dev per-band AUC, superseded by fine_dev",
    "0.2106": "retracted: the dev undetermined level, superseded",
    "0.1131": "retracted: the dev undetermined level, superseded",
    "0.0499": "retracted: the dev undetermined level, superseded",
    "0.0593": "retracted: the dev undetermined level, superseded",
    # Computed ad hoc on the holdout and never recorded. Left visible and
    # explicitly not the basis for any claim -- see the README.
    "0.9644": "retracted: an unrecorded holdout AUC",
    "0.9631": "retracted: an unrecorded holdout AUC",
    # Pre-registration figures from rounds one and five, not edited.
    "0.9489": "parameter: a pre-registration figure, not edited after the run",
    "0.934": "parameter: a round-one pre-registration figure, not edited",
    "0.958": "parameter: a round-one pre-registration figure, not edited",
}


def numbers_in_evidence() -> set[str]:
    """
    Every rendering an evidence number could legitimately take in prose.

    Rounded at zero to four decimal places, because the write-up chooses
    precision per table and a test that insisted on one would be policing
    typography rather than checking arithmetic.
    """
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            yield o

    vals: set[float] = set()
    for p in (ROOT / "evidence").glob("*.json"):
        if p.stat().st_size > 400_000:      # the case files, not results
            continue
        try:
            vals |= set(walk(json.loads(p.read_text())))
        except Exception:
            continue

    out: set[str] = set()
    for v in vals:
        for places in range(5):
            out.add(f"{v * 100:.{places}f}%")
    return out


@pytest.fixture(scope="module")
def evidence_renderings():
    r = numbers_in_evidence()
    if len(r) < 1000:
        pytest.skip("evidence/ is not populated in this checkout")
    return r


def published_percentages(doc: str) -> set[str]:
    """
    Decimal percentages only.

    Integer percentages — "5%", "20%", "100%" — are tolerances, budgets and
    shares of a design rather than measurements, and matching them would
    make the audit about parameters. One decimal place is the point at which
    a number is reporting a measurement.
    """
    text = (ROOT / doc).read_text()
    return set(re.findall(r"(?<![\d.])\d{1,3}\.\d{1,2}%", text))


@pytest.mark.parametrize("doc", DOCS)
def test_every_published_percentage_matches_an_evidence_number(
        doc, evidence_renderings):
    """
    The audit itself. A figure with no match is either in the allow-list
    with a reason, or it is a figure nothing produced.
    """
    unmatched = sorted(p for p in published_percentages(doc)
                       if p not in evidence_renderings and p not in ALLOWED)
    assert not unmatched, (
        f"{doc}: these percentages match no number in evidence/ and are not "
        f"listed in ALLOWED with a reason: {unmatched}")


def test_the_allow_list_stays_short_and_reasoned():
    """
    A guard argued away is worse than no guard.

    Every entry must carry one of the three reason codes, and the list must
    stay small — if it grows, the audit is being satisfied by exemption.
    """
    assert len(ALLOWED) <= 15, (
        "the allow-list is growing; figures are being exempted rather than "
        "sourced", sorted(ALLOWED))
    for figure, reason in ALLOWED.items():
        code = reason.split(":")[0]
        assert code in ("computed", "parameter", "retracted"), (figure, reason)
        assert len(reason) > len(code) + 3, (
            figure, "a reason code alone is not a reason")


def test_the_computed_entries_really_are_computed():
    """
    The Clopper-Pearson floors are allow-listed because library code
    produces them. That is checkable, so it is checked — otherwise
    "computed" becomes a way to exempt anything.
    """
    from abstain.group import reachable_alpha

    for figure, reason in ALLOWED.items():
        if not reason.startswith("computed: reachable_alpha"):
            continue
        n = int(re.search(r"reachable_alpha\((\d+)\)", reason).group(1))
        places = len(figure.rstrip("%").split(".")[1])
        assert f"{reachable_alpha(n) * 100:.{places}f}%" == figure, (
            figure, n, reachable_alpha(n))


def test_the_retracted_entries_are_marked_as_retracted_in_the_documents():
    """
    A figure allow-listed as retracted has to be *described* as retracted
    where it appears, or the exemption is hiding an unsourced number.
    """
    corpus = " ".join(
        " ".join((ROOT / d).read_text().split()) for d in DOCS)
    for figure, reason in ALLOWED.items():
        if not reason.startswith("retracted"):
            continue
        assert figure in corpus, (figure, "allow-listed but not published")
    for word in ("retracted", "superseded"):
        assert word in corpus.lower(), word


# ---------------------------------------------------------------------------
# The reproducing section, and the yield it reports
# ---------------------------------------------------------------------------

def test_every_script_is_listed_in_the_reproducing_section():
    """
    A script nobody can find is a result nobody can reproduce.

    Eleven of twenty-five scripts were missing from this list, all added in
    later rounds — the same drift as a hand-typed count, and the same fix:
    derive it.
    """
    text = (ROOT / "README.md").read_text()
    listed = set(re.findall(r"python (scripts/[\w.]+\.py)", text))
    have = {f"scripts/{p.name}" for p in (ROOT / "scripts").glob("*.py")}

    # run_round4.py --set holdout is deliberately absent; its dev form is
    # listed and the README says why.
    missing = sorted(have - listed)
    assert not missing, ("scripts not listed in the reproducing section",
                         missing)
    assert not sorted(listed - have), sorted(listed - have)


def test_the_readme_does_not_state_a_test_count():
    """
    Not every count should be derived; some should not be stated.

    This started as a derived count — the README said "~170 tests" at 389,
    the sixth stale count found in it. The fix looked identical to the other
    five: assert the stated number equals the collected number. It failed
    immediately, because adding that test changed the suite size it
    asserts.

    That is the distinction worth recording. The other derived counts
    measure things that change only when an experiment runs — predictions,
    bugs, AUC results, claims, advice items. A test suite's size changes
    whenever a test is added, including by the test doing the counting, so
    deriving it is circular and stating it is churn. A suite's size is not
    a result, so the README names what the suite checks and not how many
    checks there are.
    """
    text = (ROOT / "README.md").read_text()
    stated = re.search(r"pytest -q\s+#\s*(?:~)?(\d[\d,]*) tests", text)
    assert stated is None, (
        "the README states a test count; it will go stale on the next test "
        f"added, and a test asserting it changes what it counts: "
        f"{stated.group(0)!r}")
    assert "checked against the evidence" in " ".join(text.split()), \
        "say what the suite checks instead"


def test_the_yield_section_reports_what_the_guards_found():
    """
    A repository arguing for this machinery has to report what it caught,
    or the argument is unfalsifiable.

    Pinned on the specifics rather than the claim, so the section cannot
    decay into a general endorsement of its own method.
    """
    text = " ".join((ROOT / "README.md").read_text().split())
    for figure in ("314 states / 57.0%", "9.9%", "11%", "35.8%", "0.9644"):
        assert figure in text, figure
    for word in ("vacuous zero", "seven commits", "sixteen rounds", "17.5%"):
        assert word in text, word
    assert "reading found none of them" in text, \
        "the comparison is the point: scrutiny found them, reading did not"
    assert "five figures in six" in text, \
        "the audit's power is measured, so state it rather than imply the " \
        "audit catches everything"


@pytest.mark.parametrize("src_file", SOURCES)
def test_every_percentage_in_a_module_docstring_is_sourced(
        src_file, evidence_renderings):
    """
    The same audit, over the source.

    A module docstring that justifies a parameter with a measurement is
    making a published claim — `validate.refit` and
    `group.validate_groups` both do — and nothing checked those numbers
    until this test existed.
    """
    import ast
    tree = ast.parse((ROOT / src_file).read_text())
    texts = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                texts.append(doc)
    found = set()
    for t in texts:
        found |= set(re.findall(r"(?<![\d.])\d{1,3}\.\d{1,2}%", t))

    unmatched = sorted(f for f in found
                       if f not in evidence_renderings and f not in ALLOWED)
    assert not unmatched, (
        f"{src_file}: docstring percentages matching no number in evidence/ "
        f"and not in ALLOWED: {unmatched}")


def decimals_in_evidence() -> set[str]:
    """Every three- and four-place rendering of an evidence number."""
    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            yield o

    vals: set[float] = set()
    for p in (ROOT / "evidence").glob("*.json"):
        if p.stat().st_size > 400_000:
            continue
        try:
            vals |= set(walk(json.loads(p.read_text())))
        except Exception:
            continue
    return {f"{v:.{n}f}" for v in vals for n in (3, 4)}


@pytest.fixture(scope="module")
def evidence_decimals():
    d = decimals_in_evidence()
    if len(d) < 500:
        pytest.skip("evidence/ is not populated in this checkout")
    return d


@pytest.mark.parametrize("doc", DOCS + SOURCES)
def test_every_bare_decimal_is_sourced(doc, evidence_decimals):
    """
    The gap that let the per-band AUC range go unchecked.

    The percentage audit above matches percentages only, so AUCs, Kendall
    taus and concentrations — written as bare decimals — were never audited.
    One of them, 0.9976, was quoted in four documents, was in no evidence
    file, and was from the 79-case `dev` set while every other figure
    around it was `fine_dev`.
    """
    text = (ROOT / doc).read_text()
    found = set(re.findall(r"(?<![\d.])\d\.\d{3,4}(?![\d])", text))
    unmatched = sorted(f for f in found
                       if f not in evidence_decimals
                       and f not in ALLOWED_DECIMALS)
    assert not unmatched, (
        f"{doc}: bare decimals matching no number in evidence/ and not in "
        f"ALLOWED_DECIMALS with a reason: {unmatched}")


def test_the_decimal_allow_list_is_reasoned_and_bounded():
    assert len(ALLOWED_DECIMALS) <= 20, sorted(ALLOWED_DECIMALS)
    for figure, reason in ALLOWED_DECIMALS.items():
        code = reason.split(":")[0]
        assert code in ("computed", "parameter", "retracted"), (figure, reason)
        assert len(reason) > len(code) + 3, figure


def test_the_computed_decimal_is_really_the_scorers_maximum():
    """
    `rule.py` argues the refusal sentinel was unreachable because
    `handcrafted_scorer` tops out at 0.9718. That is part of the first
    bug's account, so it is checked against the function rather than
    trusted.
    """
    import json as _json
    from abstain.scorer import handcrafted_scorer
    from abstain.validate import states_of

    cases = _json.loads((ROOT / "evidence" / "dev.json").read_text())
    top = max(handcrafted_scorer(c, k) for c, k, _ in states_of(cases))
    assert f"{top:.4f}" == "0.9718", top
    assert "0.9718" in (ROOT / "src" / "abstain" / "rule.py").read_text()
