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

What this audit does not catch
------------------------------
It is one-sided. With a few thousand distinct numbers across `evidence/`,
each rendered at five precisions, a two- or three-digit percentage can match
some unrelated number by coincidence — so this catches a figure with **no
source anywhere**, not a figure attached to the wrong source. The targeted
coupling tests in `test_writeup_matches_evidence.py` do the second job, table
by table. Neither subsumes the other and the overlap is deliberate.

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
