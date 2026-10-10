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

import json
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
                          ("K", 4), ("L", 4), ("M", 5), ("N", 4),
                          ("O", 5), ("Q", 7), ("R", 5),
                          ("S", 5)):
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

    The guard needs a left boundary that a hyphen does not satisfy. With a
    plain substring test this failed the moment the count passed twenty,
    because "twenty-two" contains "two" and the test flagged the correct
    number as a stale one. `\\b` is not enough either — a hyphen is a
    non-word character, so `\\btwo` matches inside "twenty-two" as well.

    That is the same shape of defect as the `spell` lookup table that
    stopped at twelve: a check that is right over the range it was written
    against and silently wrong past it.
    """
    missed = len([p for p, _, v in ledger if outcome_of(v) == "missed"])
    text = " ".join((ROOT / "README.md").read_text().split())
    for n in range(1, missed):
        word = spell(n)
        # The full phrase, not a prefix of it: the shift section legitimately
        # says "All five pre-registered predictions held", which is a count
        # of a different thing and must not trip this.
        stale = re.compile(rf"(?<![\w-]){re.escape(word)} "
                           r"pre-registered predictions that missed")
        assert not stale.search(text), word


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


# ---------------------------------------------------------------------------
# Rounds M and N: the claim the ledger makes about them
# ---------------------------------------------------------------------------

def _arms(path: str) -> dict:
    p = ROOT / "evidence" / path
    if not p.exists():
        pytest.skip(f"{path} not present")
    return json.loads(p.read_text())


def _deployed(row: dict) -> dict:
    """Everything the run reports except what the scorer is called and AUC."""
    return {k: v for k, v in row.items() if k not in ("scorer", "auc")}


@pytest.mark.parametrize("path", ["award_aware.json", "signed_scorer.json"])
def test_the_arms_are_identical_in_every_float(path):
    """
    The claim rounds M and N rest on, checked rather than eyeballed.

    The ledger says three scorers with different AUCs produce behaviour
    "identical in every float". A printed table at one decimal place cannot
    support that — 11.47% and 11.49% both print as 11.5%. So the comparison
    is `==` over the whole reported structure: pooled rate, every band rate,
    every band's coverage, every concentration, coverage, questions per
    case, the violation rate, at every tolerance in the run.

    If a future change to the scorer or the selector makes these diverge,
    this fails and the ledger entry is wrong — which is the point. The
    result is surprising enough that it should not be allowed to rot into a
    claim nobody re-checks.
    """
    d = _arms(path)
    arms = d["arms"]
    assert "handcrafted" in arms, sorted(arms)
    others = [k for k in arms if k != "handcrafted"]
    assert others, "nothing to compare the control against"

    alphas = sorted({r["alpha"] for r in arms["handcrafted"]})
    for alpha in alphas:
        base = _deployed(next(r for r in arms["handcrafted"]
                              if r["alpha"] == alpha))
        for label in others:
            got = _deployed(next(r for r in arms[label]
                                 if r["alpha"] == alpha))
            assert got == base, (path, label, alpha)


@pytest.mark.parametrize("path", ["award_aware.json", "signed_scorer.json"])
def test_auc_moved_while_nothing_else_did(path):
    """
    The other half of the claim: AUC is not constant across these arms.

    Identical behaviour from identical scores would be unremarkable. The
    result is that the scores differ — measurably, by the metric the field
    reaches for first — and the deployed rule does not notice.
    """
    arms = _arms(path)["arms"]
    aucs = {k: v[0]["auc"] for k, v in arms.items()}
    assert len(set(aucs.values())) == len(aucs), aucs
    spread = max(aucs.values()) - min(aucs.values())
    assert spread > 0.005, (aucs, spread)


def test_the_term_fires_only_on_the_opening_state():
    """
    The mechanism behind the identity, which is the part that generalises.

    Both added terms are gated on `dependents` being unknown, and the greedy
    selector asks for `dependents` first in every case that asks anything.
    So the terms can only act on the opening state. Asserted against the
    scorers themselves rather than against prose: on any state that knows
    `dependents`, all three must agree exactly.
    """
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from abstain.scorer import (award_aware_scorer, handcrafted_scorer,
                                signed_scorer)
    from abstain.validate import states_of

    cases = json.loads((ROOT / "evidence" / "dev.json").read_text())
    checked = 0
    for case, known, _ in states_of(cases):
        if "dependents" not in known:
            continue
        h = handcrafted_scorer(case, known)
        assert award_aware_scorer(case, known) == h
        assert signed_scorer(case, known) == h
        checked += 1
    assert checked > 100, checked


def test_the_rounds_that_held_vacuously_say_so(ledger):
    """
    A cost prediction satisfied by a no-op is not a cost prediction that
    passed, and the ledger must not let it read as one.
    """
    text = " ".join(LEDGER.read_text().split())
    assert "vacuously" in text
    for label in ("M2", "N3", "N4"):
        row = next((v for p, _, v in ledger if p == label), None)
        assert row is not None, label
        assert "held" in row.lower() and "vacuous" in row.lower(), (label, row)


def test_the_opening_state_figures_are_recorded_not_typed():
    """
    The four numbers that carried rounds M and N, coupled to their run.

    "447 of 447", "225", "129" and the flip rate appeared in the
    pre-registration and in `scorer.py` before any of them existed in
    `evidence/`. A figure no script computes is a figure no test can check,
    and that is how the retracted 106,365-pair claim survived long enough to
    be committed.

    Checked against the recorded run rather than against each other, so a
    change to the selector or either scorer breaks this instead of quietly
    making the prose wrong.
    """
    p = ROOT / "evidence" / "opening_state.json"
    if not p.exists():
        pytest.skip("opening_state.json not present")
    d = json.loads(p.read_text())

    hand = d["first_question"]["handcrafted"]
    assert hand["asking_cases"]["dependents"] == hand["n_asking"], \
        "the claim is that EVERY asking case asks for dependents first"
    assert hand["all_cases"]["dependents"] == d["cases"], \
        "and that it does so independently of the threshold"

    commits = d["immediate_commits"]
    assert commits["award-aware"] == 0, commits
    assert commits["signed"] < commits["handcrafted"], commits

    corpus = " ".join(
        " ".join((ROOT / f).read_text().split())
        for f in ("docs/preregistration-5.md", "src/abstain/scorer.py",
                  "docs/predictions.md"))
    for n in (hand["n_asking"], commits["handcrafted"], commits["signed"]):
        assert f"{n:,}" in corpus or str(n) in corpus, n

    rate = d["order_flips"]["signed"]["flip_rate"]
    assert rate > 0.01, ("N1's guard", rate)
    assert f"{rate:.2%}" in corpus, \
        f"the recorded flip rate {rate:.2%} has to be the published one"


def test_the_superseded_flip_rate_is_not_silently_replaced():
    """
    An ad-hoc figure overwritten with a recorded one, with no note, would be
    the same move as replacing the retracted claim quietly.
    """
    doc = " ".join((ROOT / "docs" / "preregistration-5.md").read_text()
                   .split())
    assert "2.78%" in doc, "the superseded figure has to stay visible"
    assert "superseded" in doc
    assert "3.04%" in doc


# ---------------------------------------------------------------------------
# The bug count, which disagreed with itself inside one document
# ---------------------------------------------------------------------------

_BUG_DOCS = ("README.md", "docs/against.md", "docs/results-secondary.md")

_NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
           "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _bug_counts(path: str) -> set[int]:
    """Every count of bugs any sentence in a document claims."""
    text = " ".join((ROOT / path).read_text().split())
    found = set()
    for word, n in _NUMBER.items():
        for pat in (rf"(?<![\w-]){word} bugs?", rf"(?<![\w-])The {word} bugs?"):
            if re.search(pat, text, re.I):
                found.add(n)
    return found


def test_the_bug_count_agrees_with_itself_everywhere():
    """
    The README's opening said "four bugs" while its own section heading said
    "Three bugs", for several rounds, and the fourth was described only in a
    docstring. Two documents agreed with the heading and one with the opening.

    A count that contradicts itself inside one document is the cheapest way
    to lose a reader, and it survived because nothing compared the two. This
    compares them.
    """
    per_doc = {p: _bug_counts(p) for p in _BUG_DOCS}
    claimed = set().union(*per_doc.values())
    assert claimed, per_doc
    assert len(claimed) == 1, per_doc


def test_every_claimed_bug_has_its_own_writeup():
    """
    A count is not a record. The README must carry one subsection per bug
    under the bug section, so "four" cannot be asserted over three write-ups.
    """
    text = (ROOT / "README.md").read_text()
    counts = _bug_counts("README.md")
    n = counts.pop()

    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines)
              if re.match(r"^## .*\bbugs\b", ln, re.I)]
    assert len(starts) == 1, starts
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("## ")), len(lines))
    subs = [ln for ln in lines[start:end] if ln.startswith("### ")]
    assert len(subs) == n, (n, subs)


def test_the_advice_count_is_the_number_of_items():
    """
    The third hand-typed count in this README to go stale.

    "Seven things this project measured" sat above nine items after two
    rounds added two. Same failure as the prediction count, the bug count
    and the AUC-result count: a number typed once beside a list that grows.

    Derived from the numbered items, and the items must be consecutive from
    one, so a renumbering slip shows up here rather than in a reader's
    confusion.
    """
    lines = (ROOT / "README.md").read_text().splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("## If you are building one of these"))
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith("## "))

    nums = [int(m.group(1)) for ln in lines[start:end]
            if (m := re.match(r"^\*\*(\d+)\. ", ln))]
    assert nums, "no numbered advice items found; the section format changed"
    assert nums == list(range(1, len(nums) + 1)), nums

    # Lower-cased: the sentence opens the paragraph, so the word is
    # capitalised, and a case-sensitive match here would be checking
    # typography rather than the count.
    text = " ".join(" ".join(lines[start:end]).split()).lower()
    assert f"{spell(len(nums))} things this project measured" in text, \
        f"{len(nums)} items are listed"

    for other in range(1, 13):
        if other == len(nums):
            continue
        bad = re.compile(rf"(?<![\w-]){spell(other)} things this project")
        assert not bad.search(text), (other, len(nums))


def test_both_retractions_stay_in_the_opening():
    """
    The claims this repository published and then withdrew.

    Two: the "zero order flips in 106,365 state pairs" explanation for M1's
    failure, whose sample covered one income band, and "removing the feature
    brings every band inside the budget", which was true of the across-trial
    estimator and false of a quarter of deployments.

    They are the most credibility-relevant facts about the process here and
    the easiest to lose in an edit, because nothing else breaks when a
    sentence admitting error is dropped. So the count is asserted in the
    opening and each one has to remain findable in the documents that carry
    it.
    """
    readme = " ".join((ROOT / "README.md").read_text().split())
    assert "five claims published here and then retracted" in \
        readme.lower(), "the opening must say how many were withdrawn"
    assert "all five retractions are left visible" in readme.lower()

    prereg = " ".join(
        (ROOT / "docs" / "preregistration-5.md").read_text().split())
    assert "106,365" in prereg, "the first retraction's figure"
    assert "retracted" in prereg.lower()

    preds = " ".join((ROOT / "docs" / "predictions.md").read_text().split())
    assert "false of a quarter of deployments" in preds, \
        "the second retraction has to be in the ledger too"


def test_the_opening_states_all_three_levels_of_the_attack():
    """
    Claim, refutation, attack on the refutation — each one moved the result,
    and a reader should see the chain rather than the last link.
    """
    lines = (ROOT / "README.md").read_text().splitlines()
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "---")
    opening = " ".join(" ".join(lines[:end]).split())

    assert "attacked three levels deep" in opening
    nums = [ln for ln in lines[:end] if re.match(r"^\d+\. ", ln)]
    assert len(nums) == 3, nums
    assert "J1" in opening and "round O" in opening


def _slug(heading: str) -> str:
    """GitHub's anchor rule: lowercase, drop punctuation, spaces to hyphens."""
    s = re.sub(r"[^\w\s-]", "", heading.lower())
    return re.sub(r"\s+", "-", s.strip())


def test_the_contents_block_matches_the_actual_sections():
    """
    A hand-maintained table of contents beside a growing README is the same
    defect as a hand-typed count: it is right once.

    So it is checked. Every `##` section except Contents itself must appear
    as a link, in document order, with the anchor GitHub will actually
    generate — a wrong anchor is worse than no link, because it silently
    scrolls nowhere.
    """
    lines = (ROOT / "README.md").read_text().splitlines()
    heads = [ln[3:].strip() for ln in lines if ln.startswith("## ")]
    assert "Contents" in heads, "the contents block is missing"
    sections = [h for h in heads if h != "Contents"]
    assert len(sections) > 10, sections

    start = next(i for i, ln in enumerate(lines) if ln.strip() == "## Contents")
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith("## "))
    block = lines[start:end]

    entries = [m.groups() for ln in block
               if (m := re.match(r"^- \[(.+)\]\(#(.+)\)$", ln.strip()))]
    assert [t for t, _ in entries] == sections, (
        "the contents list and the sections disagree",
        [t for t, _ in entries], sections)
    for title, anchor in entries:
        assert anchor == _slug(title), (title, anchor, _slug(title))


def test_the_contents_block_counts_the_sections_it_lists():
    """
    The sentence above the list says how many sections there are, which is
    one more hand-typed count unless it is derived. Fifth in this README.
    """
    lines = (ROOT / "README.md").read_text().splitlines()
    heads = [ln[3:].strip() for ln in lines if ln.startswith("## ")]
    # License is listed but is not one of the sections the sentence counts.
    n = len([h for h in heads if h not in ("Contents", "License")])

    start = next(i for i, ln in enumerate(lines) if ln.strip() == "## Contents")
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith("## "))
    block = " ".join(" ".join(lines[start:end]).split()).lower()

    assert f"{spell(n)} sections and a license" in block, n
    for other in range(1, 20):
        if other == n:
            continue
        bad = re.compile(rf"(?<![\w-]){spell(other)} sections and a license")
        assert not bad.search(block), (other, n)


def test_every_in_document_link_points_at_a_real_heading():
    """
    A wrong anchor is worse than no link: it scrolls nowhere and the reader
    concludes the section does not exist.

    The README cross-references itself eighteen times and gained most of
    those while sections were being renamed, so the links are checked
    against the headings rather than trusted. Covers the whole file, not
    just the contents block.
    """
    for name in ("README.md", "docs/theory.md", "docs/against.md",
                 "docs/predictions.md", "docs/results-secondary.md"):
        text = (ROOT / name).read_text()
        anchors = {_slug(ln.lstrip("#").strip())
                   for ln in text.splitlines() if ln.startswith("#")}
        links = re.findall(r"\]\(#([^)]+)\)", text)
        broken = sorted({x for x in links if x not in anchors})
        assert not broken, (name, broken)
