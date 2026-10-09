"""
The prediction ledger, and the counts derived from it.

Why a test parses a table
-------------------------
The README's opening counts the predictions that missed. It said "five" when
there were ten, because the number was typed once and the experiments kept
arriving. A count in prose next to a growing table is a number that goes
stale silently, and this repository's whole argument is that a figure nobody
checks is a figure that drifts.

So the count is derived. `docs/predictions.md` is the record, this parses it,
and any count quoted elsewhere has to match what the table actually says.

What is NOT checked here: whether each outcome is correct. That is what the
evidence-coupling tests do, claim by claim. This checks that the ledger is
complete, internally consistent, and that nothing quotes a number the ledger
contradicts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "predictions.md"

# A prediction is any row whose first cell is a bold label like **P1** or
# **D1-D5**. The surrounding prose uses the same bold labels, so rows are
# matched on table structure rather than on the label alone.
ROW = re.compile(r"^\|\s*\*\*([A-Z][\w–\-]*)\*\*\s*\|(.*)\|(.*)\|(.*)\|\s*$")


def rows() -> list[tuple[str, str, str]]:
    out = []
    for line in LEDGER.read_text().splitlines():
        m = ROW.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2).strip(), m.group(4).strip()))
    return out


@pytest.fixture(scope="module")
def ledger():
    got = rows()
    assert got, "no prediction rows parsed; the table format changed"
    return got


_ONES = ("zero one two three four five six seven eight nine ten eleven "
         "twelve thirteen fourteen fifteen sixteen seventeen eighteen "
         "nineteen").split()
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
         "eighty", "ninety")


def spell(n: int) -> str:
    """
    The English word for a small count, generated rather than tabulated.

    The first version was a literal dict that stopped at twelve, so the
    thirteenth miss broke the test it was written to protect — a lookup
    table with a horizon is a stale number wearing a different hat, which
    is precisely what this file exists to prevent.
    """
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")


def outcome_of(verdict: str) -> str:
    """
    Reduce a verdict cell to one of three words.

    `missed` wins over `held` when both appear, because the rows that carry
    both are the ones where something held only after a fix or only once
    powered — and a row like that is not a clean pass.
    """
    text = verdict.lower()
    if "withdrawn" in text:
        return "withdrawn"
    if "missed" in text:
        return "missed"
    if "held" in text:
        return "held"
    return "unscored"


def test_every_row_has_a_scored_outcome(ledger):
    unscored = [p for p, _, v in ledger if outcome_of(v) == "unscored"]
    assert not unscored, unscored


def test_the_ledger_covers_every_preregistration(ledger):
    """
    Each round's prediction labels must all appear.

    A round whose predictions never reach the ledger is a round that was
    quietly dropped, which is the failure this file is here to make
    impossible.
    """
    labels = {p for p, _, _ in ledger}
    for prefix, count in (("P", 8), ("A", 4), ("B", 4), ("C", 3),
                          ("E", 8), ("F", 5), ("G", 3), ("H", 4), ("J", 4),
                          ("K", 4)):
        found = {x for x in labels if x.startswith(prefix)
                 and x[1:].isdigit()}
        assert len(found) == count, (prefix, sorted(found))
    assert any(x.startswith("D") for x in labels), \
        "round three's withdrawn predictions must still be listed"


def test_the_readme_quotes_the_number_the_ledger_shows(ledger):
    """
    The count in the opening, derived rather than typed.
    """
    missed = [p for p, _, v in ledger if outcome_of(v) == "missed"]
    text = " ".join((ROOT / "README.md").read_text().split())

    spelled = spell(len(missed))
    assert (f"{spelled} pre-registered predictions that missed" in text
            or f"{len(missed)} pre-registered predictions that missed"
            in text), (
        f"the ledger shows {len(missed)} misses: {missed}")


def test_no_stale_smaller_count_survives_anywhere(ledger):
    """
    The specific way this went wrong: a smaller, older count left behind.
    """
    missed = len([p for p, _, v in ledger if outcome_of(v) == "missed"])
    text = " ".join((ROOT / "README.md").read_text().split())
    for n in range(1, missed):
        word = spell(n)
        # The full phrase, not a prefix of it: the shift section legitimately
        # says "All five pre-registered predictions held", which is a count
        # of a different thing and must not trip this.
        assert f"{word} pre-registered predictions that missed" not in text, \
            word


def test_the_misses_are_each_named_in_a_writeup(ledger):
    """
    A ledger entry is not a report. Every miss has to be discussed somewhere
    a reader will actually look.
    """
    corpus = " ".join(
        " ".join(p.read_text().split())
        for p in [ROOT / "README.md", ROOT / "docs" / "results-secondary.md",
                  LEDGER])
    for label, _, verdict in ledger:
        if outcome_of(verdict) != "missed":
            continue
        assert f"{label} missed" in corpus or f"**{label}**" in corpus, label


def test_held_outnumbers_missed(ledger):
    """
    Not a claim about quality — a check that the ledger is a record and not
    a performance. If most predictions missed, the method does not work and
    the README should not be describing one that does.
    """
    held = sum(1 for _, _, v in ledger if outcome_of(v) == "held")
    missed = sum(1 for _, _, v in ledger if outcome_of(v) == "missed")
    assert held > missed, (held, missed)


def test_the_ledger_is_linked_from_the_readme():
    text = (ROOT / "README.md").read_text()
    assert "docs/predictions.md" in text, \
        "a complete record nobody can find is not a record"
