"""
Every headline number in the write-up, checked against the file that produced it.

Why this file exists
--------------------
The figures in `README.md`, `docs/theory.md` and `docs/results-secondary.md`
are transcribed by hand from run output. That is the cheapest possible way to
be wrong in the most embarrassing way: a claim in prose that the code no
longer produces, surviving because nothing checks prose.

The other tests in this suite pin *that a finding is stated*. This one pins
*that the stated figure is the measured figure*. It reads the evidence JSON,
formats each number the way the write-up formats it, and requires the string
to appear.

So a re-run that moves a number fails here until the write-up is updated,
which is the correct direction of coupling: the data is the source and the
prose follows it.

Scope, deliberately narrow
--------------------------
Only the figures a reader would act on — violation rates, the subgroup
concentration, the per-band safety and coverage pairs, the question
allocation. Pinning every number would make the suite fire on cosmetic edits
and teach whoever hits it to loosen the assertion, which is how a guard
becomes decoration.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# A `>` that begins a line is a blockquote marker, which the renderer drops.
# Leaving it in meant a phrase inside a blockquote failed to match depending
# on where the line happened to wrap — "…is defeated > by the agent…" — which
# is the typography-policing this file's own comments warn against. Stripping
# it only ever makes matching more permissive, so no existing assertion can
# be weakened by it.
_QUOTE = re.compile(r"^\s*>\s?", re.M)


def squash(path: str) -> str:
    """
    Whitespace-normalised and blockquote-stripped, so neither line wrapping
    nor markdown structure affects whether a phrase is found.
    """
    text = _QUOTE.sub("", (ROOT / path).read_text())
    return " ".join(text.split())


def count_forms(n: int) -> list[str]:
    """
    Both renderings of an integer the write-up uses.

    Prose takes a thousands separator — "1,165" — and code does not. A
    separator is formatting, not a different number, and a test that
    insisted on one would be policing typography rather than checking
    arithmetic. Same principle as `pct_forms`.
    """
    return [f"{n:,}", str(n)]


def has_count(text: str, n: int) -> bool:
    return any(form in text for form in count_forms(n))


def pct_forms(x: float, places: int = 1) -> list[str]:
    """
    Every rendering of a rate the write-up legitimately uses.

    Tables keep one decimal so columns line up — "0.0%", "100.0%" — while
    prose drops a trailing zero — "0%", "100%". Both are correct renderings
    of the same number, and a test that insisted on one would be policing
    typography rather than checking arithmetic. The job here is to catch a
    figure that CHANGED, so any faithful form passes.
    """
    exact = f"{x * 100:.{places}f}"
    forms = [exact + "%"]
    if exact.endswith(".0"):
        forms.append(exact[:-2] + "%")
    return forms


class _Pct(str):
    """Lets `pct(v) in readme` read naturally while accepting either form."""

    def __new__(cls, x: float, places: int = 1):
        forms = pct_forms(x, places)
        self = super().__new__(cls, forms[0])
        self.forms = forms
        return self


def pct(x: float, places: int = 1) -> "_Pct":
    return _Pct(x, places)


class _Haystack(str):
    """
    A string whose `in` test understands `pct`.

    `pct(v) in readme` is the readable form and appears dozens of times
    below; this keeps that phrasing while letting a value match any
    rendering the write-up legitimately uses.
    """

    def __contains__(self, needle) -> bool:
        forms = getattr(needle, "forms", None) or [needle]
        return any(str.__contains__(self, f) for f in forms)


@pytest.fixture(scope="module")
def readme():
    return _Haystack(squash("README.md"))


@pytest.fixture(scope="module")
def theory():
    return _Haystack(squash("docs/theory.md"))


@pytest.fixture(scope="module")
def round4():
    p = ROOT / "evidence" / "round4_dev.json"
    if not p.exists():
        pytest.skip("round four has not been run in this checkout")
    return json.loads(p.read_text())


@pytest.fixture(scope="module")
def bands():
    """
    The per-band figures live in round five's output, not round four's.

    Round four ran before `GroupValidation` accumulated per-band counts, and
    re-running it to pick them up would have cost another twenty-two minutes
    for numbers round five already produces on the same set with the same
    seed and trial count. So the per-band assertions read the file that has
    them, and `test_the_two_runs_agree` below checks the two runs agree where
    they overlap — which is what makes reading across them safe.
    """
    p = ROOT / "evidence" / "round5_shift.json"
    if not p.exists():
        pytest.skip("round five has not been run in this checkout")
    return json.loads(p.read_text())["per_band"]


@pytest.fixture(scope="module")
def allocation():
    """
    Questions per case, per band — from its own recorded run.

    The per-band fixture above comes from round five, which ran before
    `GroupValidation` tracked questions per band. Rather than quote the
    allocation figures from an ad-hoc run with no file behind it — which is
    what the README did until this test caught it — `scripts/run_allocation.py`
    produces them at round four's trial count and seed, and they are read
    from there.
    """
    p = ROOT / "evidence" / "allocation.json"
    if not p.exists():
        pytest.skip("the allocation run has not happened in this checkout")
    return json.loads(p.read_text())["runs"]


def band_row(bands: list[dict], scheme: str, alpha: float,
             band: str) -> dict:
    s = next(x for x in bands
             if x["scheme"] == scheme and x["alpha"] == alpha)
    return next(r for r in s["bands"] if r["band"] == band)


@pytest.fixture(scope="module")
def postfix():
    p = ROOT / "evidence" / "corruption_postfix.json"
    if not p.exists():
        pytest.skip("the corruption re-run has not happened in this checkout")
    return json.loads(p.read_text())


# ---------------------------------------------------------------------------
# The replication
# ---------------------------------------------------------------------------

def test_replication_violations_are_as_written(readme, round4):
    for row in round4["E1_E2_replication"]:
        v = row["violation_rate_when_feasible"]
        assert v is not None, row["alpha"]
        assert pct(v) in readme, (row["alpha"], pct(v))


def test_replication_coverage_is_as_written(readme, round4):
    for row in round4["E1_E2_replication"]:
        assert pct(row["mean_coverage"]) in readme, row["alpha"]


def test_the_replication_size_is_as_written(readme, round4):
    assert round4["n_cases"] == 672
    assert str(round4["trials"]) in readme
    assert "672" in readme


# ---------------------------------------------------------------------------
# The finding at the top of the README
# ---------------------------------------------------------------------------

def test_the_headline_pair_is_as_measured(readme, round4):
    """
    "Honoured overall in 98.5% of trials, broken for some band in 98.2%."

    Both halves come from the same run and the pair is the point, so both are
    checked. The first is one minus the pooled violation rate at alpha = 0.20;
    the second is the per-band violation rate for the same scheme.
    """
    pooled = next(s for s in round4["E4_E7_schemes"]
                  if s["scheme"] == "pooled" and s["alpha"] == 0.20)
    overall_pass = 1.0 - pooled["violation_rate_when_feasible"]
    per_band_fail = pooled["group_violation_rate_when_feasible"]

    assert pct(overall_pass) in readme, pct(overall_pass)
    assert pct(per_band_fail) in readme, pct(per_band_fail)


def test_the_concentration_figures_are_as_measured(readme, round4):
    at20 = next(c for c in round4["E3_E8_concentration"]
                if c["alpha"] == 0.20)
    worst = at20["worst_band"]
    assert worst == "well-below"
    assert at20["hides_a_subgroup"] is True

    band = next(b for b in at20["bands"] if b["band"] == worst)
    assert pct(band["unsafe_rate"]) in readme
    assert pct(at20["pooled_unsafe_rate"]) in readme

    conc = at20["concentration"][worst]
    assert f"{conc:.1f}" in readme or f"{conc:.2f}" in readme, conc


def test_the_scheme_comparison_is_as_measured(readme, round4):
    for scheme in ("pooled", "by-band"):
        s = next(x for x in round4["E4_E7_schemes"]
                 if x["scheme"] == scheme and x["alpha"] == 0.20)
        assert pct(s["group_violation_rate_when_feasible"]) in readme, scheme
        assert pct(s["mean_worst_group_rate"]) in readme, scheme
        assert pct(s["mean_coverage"]) in readme, scheme
        assert f"{s['mean_questions']:.2f}" in readme, scheme


def test_the_per_band_pairs_are_as_measured(readme, bands):
    """
    The `well-below` before/after table, which is the project's result.
    """
    for scheme in ("pooled", "by-band"):
        wb = band_row(bands, scheme, 0.20, "well-below")
        assert pct(wb["unsafe_rate"]) in readme, (scheme, "unsafe")
        assert pct(wb["coverage"]) in readme, (scheme, "coverage")
        assert pct(wb["abstention_rate"]) in readme, (scheme, "abstention")


def test_the_question_allocation_table_is_as_measured(readme, allocation):
    """
    The mechanism: which band gets asked how much, under each scheme.
    """
    for scheme in ("pooled", "by-band"):
        for band in ("well-below", "near-threshold", "above", "well-above"):
            q = band_row(allocation, scheme, 0.20,
                         band)["questions_per_case"]
            assert f"{q:.2f}" in readme, (scheme, band, q)


def test_the_reallocation_lowers_the_total(readme, allocation):
    """
    Fewer questions overall while asking more where they are needed.

    Without this the finding would be "it asks more of the failing band",
    which is unsurprising. The total falling is what makes it a
    mis-allocation rather than an under-allocation.
    """
    totals = {}
    for scheme in ("pooled", "by-band"):
        s = next(x for x in allocation
                 if x["scheme"] == scheme and x["alpha"] == 0.20)
        totals[scheme] = s["mean_questions"]
    assert totals["by-band"] < totals["pooled"]
    for v in totals.values():
        assert f"{v:.2f}" in readme, v


def test_the_global_threshold_underasks_the_failing_band(allocation):
    """
    The claim stated as an inequality rather than a pair of numbers.

    A single global threshold asks FEWER questions of the band with the
    highest unsafe rate than of a band with a low one. If that ever reverses,
    "mis-allocates questions in exactly the wrong direction" is wrong.
    """
    worst = band_row(allocation, "pooled", 0.20, "well-below")
    comfortable = band_row(allocation, "pooled", 0.20, "well-above")
    assert worst["unsafe_rate"] > comfortable["unsafe_rate"] * 5
    assert worst["questions_per_case"] < comfortable["questions_per_case"]

    # And conditioning reverses it.
    fixed_worst = band_row(allocation, "by-band", 0.20, "well-below")
    fixed_comfortable = band_row(allocation, "by-band", 0.20, "well-above")
    assert fixed_worst["questions_per_case"] > \
        fixed_comfortable["questions_per_case"]


def test_the_zero_abstention_claim_is_true_not_rhetorical(bands):
    """
    The README says the pooled rule never abstains on `well-below`.

    If that is ever not exactly zero, the sentence is wrong and has to change,
    because "never" is doing real work in it.
    """
    assert band_row(bands, "pooled", 0.20,
                    "well-below")["abstention_rate"] == 0.0


def test_safety_and_coverage_both_improve_for_the_failing_band(bands):
    """
    The claim that this is not a trade-off, asserted on the data.

    If a re-run ever shows coverage falling for `well-below` while safety
    improves, the README's framing is wrong and this fails rather than the
    framing quietly surviving.
    """
    before = band_row(bands, "pooled", 0.20, "well-below")
    after = band_row(bands, "by-band", 0.20, "well-below")
    assert after["unsafe_rate"] < before["unsafe_rate"]
    assert after["coverage"] > before["coverage"]


def test_the_cost_lands_on_well_above_and_is_reported(readme, bands):
    """
    Conditioning is not free for every band, and the README has to say so.

    `well-above` was over-protected by a threshold set for another band and
    now spends its own budget: its unsafe rate rises. A write-up that
    reported only the bands that improved would be selecting its evidence.
    """
    before = band_row(bands, "pooled", 0.20, "well-above")
    after = band_row(bands, "by-band", 0.20, "well-above")
    assert after["unsafe_rate"] > before["unsafe_rate"]
    assert pct(after["unsafe_rate"]) in readme
    assert after["unsafe_rate"] < 0.20, \
        "and it must still be inside the budget, or it is not a cost but a " \
        "failure"


def test_the_two_runs_agree_where_they_overlap(round4, bands):
    """
    Round four and round five share a set, seed and trial count, so the
    figures they both produce must match.

    This is what makes it safe for the write-up to quote per-band numbers
    from one run and pooled numbers from the other. If the two ever diverge,
    quoting across them is quoting two different experiments.
    """
    for scheme in ("pooled", "by-band"):
        four = next(x for x in round4["E4_E7_schemes"]
                    if x["scheme"] == scheme and x["alpha"] == 0.20)
        five = next(x for x in bands
                    if x["scheme"] == scheme and x["alpha"] == 0.20)
        assert four["feasible_trials"] == five["feasible_trials"], scheme
        assert four["mean_coverage"] == pytest.approx(
            five["mean_coverage"], abs=1e-9), scheme
        assert four["mean_worst_group_rate"] == pytest.approx(
            five["mean_worst_group_rate"], abs=1e-9), scheme


# ---------------------------------------------------------------------------
# The corruption study
# ---------------------------------------------------------------------------

def test_no_corruption_violates_when_feasible(postfix):
    """
    The claim is "nothing violates", so it is checked over the whole run
    rather than over the rows that got quoted.

    `holds` carries the acceptance slack, widened by the feasible trial count,
    and is None where nothing was feasible — which is not a pass and not a
    failure.
    """
    for r in postfix["runs"]:
        if r["holds"] is None:
            assert r["feasible_trials"] == 0, r["corruption"]
            continue
        assert r["holds"] is True, (r["corruption"], r["alpha"],
                                    r["violation_rate_when_feasible"])


def test_the_adversarial_scorer_declines_rather_than_violating(postfix):
    """
    Post-fix, `inverted` and `constant` must have no feasible trial at all.

    Pre-fix they were feasible and violated in 100% of trials, because the
    refusal threshold was reachable. This is the behavioural pin on that fix,
    at the level of the reported evidence rather than the unit test.
    """
    for name in ("inverted", "constant"):
        rows = [r for r in postfix["runs"] if r["corruption"] == name]
        assert rows, name
        for r in rows:
            assert r["feasible_trials"] == 0, (name, r["alpha"])
            assert r["violation_rate_when_feasible"] is None


def test_the_language_model_proxy_numbers_are_as_written(readme, postfix):
    """
    The two figures that answer "no model was run" quantitatively: what
    rounding costs, and what mild rank noise costs.
    """
    for name in ("coarse(0.1)", "noisy(0.10)"):
        row = next(r for r in postfix["runs"]
                   if r["corruption"] == name and r["alpha"] == 0.20)
        assert pct(row["mean_coverage"]) in readme, name

    ident = next(r for r in postfix["runs"]
                 if r["corruption"] == "identity" and r["alpha"] == 0.20)
    assert pct(ident["mean_coverage"]) in readme


def test_sharpen_really_is_auc_identical(postfix):
    """
    The second of the three AUC results. If the transform stopped being
    monotone the claim would be mislabelled.
    """
    ident = next(r for r in postfix["runs"] if r["corruption"] == "identity")
    sharp = next(r for r in postfix["runs"]
                 if r["corruption"] == "sharpen(0.25)")
    assert sharp["auc"] == pytest.approx(ident["auc"], abs=1e-12)
    assert sharp["kendall_tau"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# The theory document says the same things as the README
# ---------------------------------------------------------------------------

def test_theory_and_readme_agree_on_the_headline_pair(theory, readme, round4):
    pooled = next(s for s in round4["E4_E7_schemes"]
                  if s["scheme"] == "pooled" and s["alpha"] == 0.20)
    for value in (pct(1.0 - pooled["violation_rate_when_feasible"]),
                  pct(pooled["group_violation_rate_when_feasible"])):
        assert value in readme, value
        assert value in theory, value


def test_theory_does_not_carry_a_claim_the_readme_retracted(theory, readme,
                                                            fitted_cond):
    """
    The specific way these two documents came apart.

    `theory.md` claimed the concentration is "a property of using one
    threshold rather than a property of this scorer" and kept claiming it for
    two rounds after J1 refuted it and the README said so. A stale claim in
    the theory file is worse than one in a write-up, because the theory file
    is what a reader checks the write-up against — so the agreement is
    asserted rather than hoped for.

    Pinned on the refutation's own numbers, which come from the J-round run,
    plus the absence of the retracted sentence outside its strike-through.
    """
    raw = (ROOT / "docs" / "theory.md").read_text()
    squashed = squash("docs/theory.md")

    claim = ("property of using one threshold rather than a "
             "property of this scorer")
    # Strip the struck-through block before looking: the old claim is SUPPOSED
    # to appear there. What must not happen is it appearing as live prose.
    live = re.sub(r"~~.*?~~", "", squashed, flags=re.S)
    assert claim not in live, "the retracted claim is being asserted again"
    assert claim in squashed, \
        "and it must still be visible as the thing that was retracted"

    assert "Refuted by its own pre-registered test (J1)" in squashed
    assert "~~" in raw, \
        "the retraction strikes the old claim through rather than deleting it"

    nodist = arm(fitted_cond, "fitted-no-distance", 0.20)
    hand = arm(fitted_cond, "handcrafted", 0.20)
    for name, payload in (("theory", theory), ("readme", readme)):
        for row in (nodist, hand):
            value = f"{row['concentration'][row['worst_band']]:.2f}"
            assert value in payload, (name, value)


def test_theory_carries_the_sequential_caution_result(theory):
    """
    Rounds M and N belong in the theory document too, not only the README.

    The result is about what a confidence function means for a sequential
    rule, which is a claim about the method rather than about this benchmark,
    so it is §4's business.
    """
    assert "defeated by the agent resolving that unknown" in theory
    assert "0.9604" in theory and "0.9425" in theory
    assert "447" in theory


def test_theory_states_the_marginal_limit_as_a_numbered_claim(theory):
    """
    It used to be a bullet under "what none of this covers". A caveat worth
    98.5% against 98.2% is not a caveat.
    """
    assert "## 4. The guarantee is marginal, not conditional" in \
        (ROOT / "docs" / "theory.md").read_text()
    assert "Four claims appear in this repository" in theory


# ---------------------------------------------------------------------------
# The shift sweep
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shift():
    p = ROOT / "evidence" / "round5_shift.json"
    if not p.exists():
        pytest.skip("round five has not been run in this checkout")
    return json.loads(p.read_text())["shift"]["sweep"]


def point(sweep: dict, scheme: str, alpha: float, share: float) -> dict:
    return next(p for p in sweep["points"]
                if p["scheme"] == scheme and p["alpha"] == alpha
                and p["target_share"] == share)


def test_the_shift_table_is_as_measured(readme, shift):
    for share in (0.143, 0.25, 0.40, 0.60, 0.80, 1.00):
        for scheme in ("pooled", "by-band"):
            p = point(shift, scheme, 0.20, share)
            assert p["violation_rate"] is not None, (scheme, share)
            assert pct(p["violation_rate"]) in readme, (scheme, share)


def test_the_pooled_rule_collapses_under_shift(shift):
    """F2 and F3 as inequalities, not as quoted values."""
    rates = [point(shift, "pooled", 0.20, s)["violation_rate"]
             for s in (0.143, 0.25, 0.40, 0.60, 0.80, 1.00)]
    assert rates == sorted(rates), rates
    assert rates[0] <= 0.05, "F1: the control has to hold"
    assert rates[-1] > 0.80, "F3: full shift must break it badly"


def test_group_conditioning_survives_the_shift(shift):
    """
    F4, the prediction worth the round.

    Stated as the inequality rather than the numbers: group conditioning must
    stay inside delta at every shift level, and must be far better than the
    pooled rule at full shift. If this ever fails, the claim that the fairness
    finding and the robustness finding are one finding is withdrawn.
    """
    for share in (0.143, 0.25, 0.40, 0.60, 0.80, 1.00):
        g = point(shift, "by-band", 0.20, share)["violation_rate"]
        assert g is not None and g <= 0.05, (share, g)

    pooled = point(shift, "pooled", 0.20, 1.00)["violation_rate"]
    grouped = point(shift, "by-band", 0.20, 1.00)["violation_rate"]
    assert grouped < pooled / 5, (grouped, pooled)


def test_the_reported_bound_does_not_move(readme, shift):
    """
    F5: the failure is silent.

    The bound is computed on unshifted calibration data, so it must be
    identical at every shift level while the deployed rate climbs. That
    identity is the finding — an operator watching the certificate sees
    nothing.
    """
    bounds = {point(shift, "pooled", 0.20, s)["mean_reported_bound"]
              for s in (0.143, 0.25, 0.40, 0.60, 0.80, 1.00)}
    assert len(bounds) == 1, bounds

    bound = bounds.pop()
    assert f"{bound:.3f}" in readme, bound

    # And the gap it hides, so the test fails if the sweep ever stops being
    # alarming rather than only if the bound starts moving.
    worst = point(shift, "pooled", 0.20, 1.00)["mean_unsafe_rate"]
    assert worst > bound * 2, (worst, bound)


def test_the_resampling_limitation_is_reported(readme, shift):
    """
    Forcing a 14.3% band to 80% of the fold needs replacement, so the
    high-shift rows rest on fewer distinct cases. The README has to say so.
    """
    full = point(shift, "pooled", 0.20, 1.00)["distinct_fraction"]
    natural = point(shift, "pooled", 0.20, 0.143)["distinct_fraction"]
    assert full < natural
    assert pct(full) in readme, full


# ---------------------------------------------------------------------------
# The figure
# ---------------------------------------------------------------------------

def test_the_figure_is_not_older_than_its_source():
    """
    A figure is the part of a write-up a reader trusts most and checks least.

    `docs/shift.svg` is generated from `evidence/round5_shift.json`. If the
    evidence is regenerated and the figure is not, the picture silently
    disagrees with the table beside it — so a stale figure is a failure here
    rather than something a reader has to notice.
    """
    svg = ROOT / "docs" / "shift.svg"
    src = ROOT / "evidence" / "round5_shift.json"
    if not svg.exists() or not src.exists():
        pytest.skip("figure or its source not present in this checkout")
    assert svg.stat().st_mtime >= src.stat().st_mtime, \
        "regenerate with scripts/make_figure.py"


def test_the_figure_carries_the_numbers_it_claims(shift):
    """
    The three figures the picture asserts, checked against the sweep.

    Pinned because a chart can drift from its data in ways no reader will
    catch: an axis rescaled, a label left over from a previous run.
    """
    svg = ROOT / "docs" / "shift.svg"
    if not svg.exists():
        pytest.skip("figure not present in this checkout")
    text = svg.read_text()

    first = point(shift, "pooled", 0.20, 0.143)["violation_rate"]
    last = point(shift, "pooled", 0.20, 1.00)["violation_rate"]
    grouped = point(shift, "by-band", 0.20, 1.00)["violation_rate"]
    bound = point(shift, "pooled", 0.20, 1.00)["mean_reported_bound"]

    assert pct(first) in text
    assert f"{last * 100:.0f}%" in text
    assert pct(grouped) in text
    assert f"{bound:.3f}" in text


def test_the_figure_is_accessible_and_self_describing():
    """
    It is referenced from the README as an image, so its alt text is the
    only thing a screen reader or a text-only view gets. The SVG carries its
    own description too, for anyone opening the file directly.
    """
    svg = ROOT / "docs" / "shift.svg"
    if not svg.exists():
        pytest.skip("figure not present in this checkout")
    text = svg.read_text()
    assert 'role="img"' in text
    assert 'aria-label="' in text
    assert len(text.split('aria-label="')[1].split('"')[0]) > 120, \
        "the label has to describe the finding, not name the chart"

    readme = (ROOT / "README.md").read_text()
    assert "docs/shift.svg" in readme
    alt = readme.split("![", 1)[1].split("]", 1)[0]
    assert len(" ".join(alt.split())) > 80, \
        "the README's alt text has to carry the finding too"


def test_the_figure_colours_survive_a_renderer_that_ignores_css():
    """
    Dark theme is a CSS override on top of explicit attributes, not the only
    source of colour.

    The first version set every neutral through CSS custom properties, which
    a non-browser renderer dropped — the figure came out with black gridlines
    and was only noticed because it was proofed outside a browser. Light
    theme must therefore be readable with the stylesheet thrown away.
    """
    svg = ROOT / "docs" / "shift.svg"
    if not svg.exists():
        pytest.skip("figure not present in this checkout")
    body = svg.read_text().split("</style>", 1)[-1]
    assert "var(--" not in body, \
        "no colour in the body may depend on a CSS custom property"
    assert body.count('fill="#') > 10
    assert 'stroke="#d8dee4"' in body, "gridlines need a literal light value"


# ---------------------------------------------------------------------------
# The mechanism, and the hypothesis that was rejected
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mechanism():
    p = ROOT / "evidence" / "mechanism.json"
    if not p.exists():
        pytest.skip("the mechanism diagnosis has not been run")
    return json.loads(p.read_text())


def amount_share(split: dict, band: str) -> float:
    d = split[band]
    total = d["flip"] + d["amount_only"]
    return d["amount_only"] / total if total else 0.0


def test_the_two_populations_give_opposite_answers(mechanism):
    """
    The correction, pinned from both sides.

    Asked of ALL undetermined states, `well-below` is 31% amount-only and
    the hypothesis looks rejected. Asked of the states the rule actually
    COMMITS on, it is 72% and the hypothesis is substantially right.

    Both numbers have to stay true for the correction to make sense: if the
    all-states figure ever rose above half, the original rejection would
    never have happened and the story about walking into a selection effect
    would be fiction.
    """
    commits = mechanism.get("criterion_split_of_commits")
    if not commits:
        pytest.skip("this run predates the commit-population measurement")

    assert amount_share(mechanism["criterion_split"], "well-below") < 0.5
    assert amount_share(commits, "well-below") > 0.65
    assert amount_share(commits, "well-below") > \
        2 * amount_share(mechanism["criterion_split"], "well-below")


def test_the_correction_is_stated_not_silently_applied(readme, mechanism):
    """
    An earlier conclusion was wrong. Replacing it quietly would be the one
    move this repository argues against throughout.
    """
    commits = mechanism.get("criterion_split_of_commits")
    if not commits:
        pytest.skip("this run predates the commit-population measurement")

    text = " ".join((ROOT / "README.md").read_text().split())
    # The claim, not one phrasing of it. This assertion was written against
    # the first correction ("the rejection was wrong") and had to change when
    # that correction was itself corrected — which is the argument for
    # pinning the figures and the admission, not the sentence.
    assert "72%, not 31%" in text
    assert "over-corrected" in text, \
        "the second revision has to be visible, not silently applied"
    assert "three passes" in text

    wb = commits["well-below"]
    assert has_count(text, wb["flip"] + wb["amount_only"])
    assert has_count(text, wb["amount_only"])

    source = (ROOT / "scripts" / "diagnose_mechanism.py").read_text()
    assert "CORRECTION" in source, \
        "the script carrying the wrong rejection has to carry the correction"


def test_the_failing_band_never_scores_zero(mechanism, readme):
    """
    The sharp fact the mechanism rests on.

    Every other band has undetermined states the scorer rates at zero — it
    knows it cannot tell. In `well-below` there are none, and the median is
    the highest of any band.
    """
    prof = mechanism["score_profile"]
    wb = prof["well-below"]
    assert wb["share_scoring_zero"] == 0.0
    assert all(wb["median_score"] >= prof[b]["median_score"]
               for b in prof), "well-below must have the highest median"
    assert all(wb["mean_log_distance"] >= prof[b]["mean_log_distance"]
               for b in prof), "and the largest distance-from-boundary"

    assert f"{wb['median_score']:.4f}" in readme
    assert f"{wb['mean_log_distance']:.4f}" in readme


def test_the_scorer_is_right_about_its_own_question(mechanism):
    """
    The corrected mechanism in one assertion.

    Most of what the rule gets wrong in `well-below` is not eligibility — it
    is the award. So the scorer, which estimates whether *eligibility* is
    settled, is largely correct about the question it answers and wrong
    about the one it is scored on. If its commitments there were mostly
    eligibility flips, that framing would be wrong.
    """
    commits = mechanism.get("criterion_split_of_commits")
    if not commits:
        pytest.skip("this run predates the commit-population measurement")
    assert amount_share(commits, "well-below") > 0.5


# ---------------------------------------------------------------------------
# The confound: is it the stopping rule or the asking rule?
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def confounds():
    p = ROOT / "evidence" / "confounds.json"
    if not p.exists():
        pytest.skip("the confound check has not been run")
    return json.loads(p.read_text())["rows"]


def row(rows: list[dict], policy: str, alpha: float) -> dict:
    return next(r for r in rows if r["policy"] == policy
                and r["alpha"] == alpha)


def test_the_same_band_fails_under_every_question_policy(confounds):
    """
    The claim that the finding is a threshold property.

    If a question policy that cannot be serving any band strategically — a
    fixed order blind to the case, or a random one — produced a different
    worst band, the subgroup result would be about what the agent asks rather
    than about when it stops.
    """
    for alpha in (0.20, 0.15):
        for policy in ("greedy (default)", "fixed order", "random order"):
            r = row(confounds, policy, alpha)
            assert r["worst_band"] == "well-below", (policy, alpha)
            assert r["concentration"] > 2.0, (policy, alpha)
            assert r["hides_a_subgroup"] is True, (policy, alpha)


def test_randomising_the_question_order_does_not_fix_it(confounds, readme):
    """
    And it is not merely that the band still fails — changing the policy
    buys almost nothing and costs questions.

    At alpha = 0.15 the random order is *worse* for the failing band than
    the greedy one, which is the sharpest form of "you cannot fix this by
    changing what you ask".
    """
    greedy20 = row(confounds, "greedy (default)", 0.20)
    random20 = row(confounds, "random order", 0.20)
    assert random20["questions_per_case"] > greedy20["questions_per_case"]
    gain = greedy20["well_below_unsafe_rate"] - \
        random20["well_below_unsafe_rate"]
    assert gain < 0.05, "a large gain would make this a policy problem"

    greedy15 = row(confounds, "greedy (default)", 0.15)
    random15 = row(confounds, "random order", 0.15)
    assert random15["well_below_unsafe_rate"] > \
        greedy15["well_below_unsafe_rate"]

    assert pct(random20["well_below_unsafe_rate"]) in readme
    assert f"{random20['questions_per_case']:.2f}" in readme


def test_the_greedy_policy_is_a_constant_order(confounds):
    """
    Greedy and the case-blind fixed order come out bit-identical.

    The scorer's penalties for unknown fields are case-independent constants,
    so the expected one-step gain ranks the same way for every case and the
    lookahead never adapts. Pinned because the README says so, and because a
    future scorer with case-dependent penalties would break the claim without
    breaking anything else.
    """
    for alpha in (0.20, 0.15):
        g = row(confounds, "greedy (default)", alpha)
        f = row(confounds, "fixed order", alpha)
        for key in ("pooled_unsafe_rate", "well_below_unsafe_rate",
                    "concentration", "questions_per_case"):
            assert g[key] == pytest.approx(f[key], abs=1e-12), (key, alpha)


def test_every_script_in_the_reproduce_block_exists(readme):
    """
    A reproduce section that names a script which is not there is worse than
    none: it reads as rigour and fails on first use.
    """
    import re
    block = (ROOT / "README.md").read_text()
    named = set(re.findall(r"python (scripts/[\w_]+\.py)", block))
    assert len(named) >= 8, named
    for script in named:
        assert (ROOT / script).exists(), script


def test_the_holdout_script_is_excluded_from_the_reproduce_block(readme):
    """
    The one script a reader must not run casually.
    """
    import re
    block = (ROOT / "README.md").read_text()
    runnable = re.findall(r"^python (scripts/[\w_]+\.py)(.*)$", block,
                          re.MULTILINE)
    for script, args in runnable:
        assert "--set holdout" not in args, script
    assert "deliberately not in that list" in " ".join(block.split())


def test_the_pinned_oracle_in_the_readme_matches_the_data(readme):
    meta = json.loads(
        (ROOT / "evidence" / "cases_fine.meta.json").read_text())
    assert meta["engine"] in readme, meta["engine"]


# ---------------------------------------------------------------------------
# The holdout, which is now what the README leads with
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def holdout():
    p = ROOT / "evidence" / "round4_holdout.json"
    if not p.exists():
        pytest.skip("the holdout has not been opened in this checkout")
    return json.loads(p.read_text())


def test_the_headline_pair_comes_from_the_holdout(readme, holdout):
    """
    The README leads with held-out numbers, not development ones.

    Pinned because leading with the weaker set would be the easiest
    unremarked downgrade in the document.
    """
    pooled = next(s for s in holdout["E4_E7_schemes"]
                  if s["scheme"] == "pooled" and s["alpha"] == 0.20)
    overall_pass = 1.0 - pooled["violation_rate_when_feasible"]
    per_band_fail = pooled["group_violation_rate_when_feasible"]

    assert pct(overall_pass) in readme, pct(overall_pass)
    assert pct(per_band_fail) in readme, pct(per_band_fail)
    assert "held-out" in readme or "holdout" in readme


def test_the_holdout_is_worse_than_dev_and_the_readme_says_so(
        readme, round4, holdout):
    """
    The direction matters more than the magnitude.

    A result that degrades from dev to holdout is the usual sign of tuning;
    one that worsens *against* the method cannot be. The README claims that
    and it has to be true.
    """
    def worst(payload) -> float:
        c = next(x for x in payload["E3_E8_concentration"]
                 if x["alpha"] == 0.20)
        return next(b["unsafe_rate"] for b in c["bands"]
                    if b["band"] == c["worst_band"])

    assert worst(holdout) > worst(round4)
    assert pct(worst(holdout)) in readme
    assert pct(worst(round4)) in readme, \
        "the dev figure must still be shown for comparison"
    assert "The holdout is worse" in readme


def test_the_same_band_fails_on_holdout(holdout):
    for c in holdout["E3_E8_concentration"]:
        assert c["worst_band"] == "well-below", c["alpha"]
        assert c["hides_a_subgroup"] is True, c["alpha"]


def test_group_conditioning_replicates_on_holdout(holdout):
    """
    E5 and the E6 reversal, on data neither was developed against.
    """
    for alpha in (0.20, 0.15):
        pooled = next(s for s in holdout["E4_E7_schemes"]
                      if s["scheme"] == "pooled" and s["alpha"] == alpha)
        band = next(s for s in holdout["E4_E7_schemes"]
                    if s["scheme"] == "by-band" and s["alpha"] == alpha)

        # E5: far fewer trials break some band's budget.
        assert band["group_violation_rate_when_feasible"] < \
            pooled["group_violation_rate_when_feasible"] / 5, alpha
        # E6 reversed: coverage up, not down, and fewer questions.
        assert band["mean_coverage"] > pooled["mean_coverage"], alpha
        assert band["mean_questions"] < pooled["mean_questions"], alpha


def test_the_post_hoc_scheme_does_not_generalise(holdout):
    """
    `separate-well-below` was chosen after seeing which band failed, and the
    pre-registration said that makes it fitted to this benchmark.

    On holdout it sits far nearer the pooled rule than the full scheme does,
    which is what "fitted" predicts: separating the group you know fails
    leaves the groups you did not check sharing a threshold.
    """
    at20 = {s["scheme"]: s for s in holdout["E4_E7_schemes"]
            if s["alpha"] == 0.20}
    post = at20["separate-well-below"]
    full = at20["by-band"]
    assert post["post_hoc"] is True
    assert post["group_violation_rate_when_feasible"] > \
        full["group_violation_rate_when_feasible"] * 5


# ---------------------------------------------------------------------------
# "Just recalibrate" — the rebuttal, and what survives it
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def recal():
    p = ROOT / "evidence" / "recalibration.json"
    if not p.exists():
        pytest.skip("the recalibration run has not happened")
    return json.loads(p.read_text())


def rpoint(payload: dict, label: str, scheme: str, share: float) -> dict:
    return next(p for p in payload[label]["points"]
                if p["scheme"] == scheme and p["target_share"] == share)


def test_recalibration_fixes_validity(readme, recal):
    """
    G1, as the inequality it is: a large, monotone-ish improvement.

    Not "at or below delta everywhere", because that is what G1 predicted and
    it is not what happened. The claim the write-up makes is the 10x
    improvement, and that is what is pinned.
    """
    for share in (0.25, 0.40, 0.60, 0.80, 1.00):
        stale = rpoint(recal, "stale", "pooled", share)["violation_rate"]
        fresh = rpoint(recal, "recalibrated", "pooled",
                       share)["violation_rate"]
        assert fresh < stale, share
        assert pct(fresh) in readme, (share, fresh)

    worst_stale = rpoint(recal, "stale", "pooled", 1.00)["violation_rate"]
    worst_fresh = rpoint(recal, "recalibrated", "pooled",
                         1.00)["violation_rate"]
    assert worst_fresh < worst_stale / 5


def test_g1_is_recorded_as_a_miss(readme, recal):
    """
    It predicted delta at every level. Three levels are above it.

    Pinned so the miss cannot quietly vanish from a later edit, and so that
    a future run which *does* meet delta everywhere forces the write-up to
    stop calling it a miss.
    """
    above = [s for s in (0.143, 0.25, 0.40, 0.60, 0.80, 1.00)
             if rpoint(recal, "recalibrated", "pooled",
                       s)["violation_rate"] > 0.05]
    assert above, "G1 now holds everywhere; the write-up must be updated"
    assert "**G1 missed.**" in (ROOT / "README.md").read_text()


def test_recalibration_does_nothing_for_the_subgroup_failure(readme, recal):
    """
    G3, which is the point of the whole round.

    At the mix an operator actually faces, a freshly recalibrated pooled rule
    must still concentrate — and must do so at essentially the same magnitude
    as the stale one, or "recalibration does nothing for it" is too strong.
    """
    fresh = rpoint(recal, "recalibrated", "pooled", 0.143)
    assert fresh["hides_a_subgroup"] is True
    assert fresh["worst_band_rate"] > 0.20, "must exceed the tolerance"
    assert fresh["max_concentration"] > 3.5

    stale = rpoint(recal, "stale", "pooled", 0.143)
    assert abs(fresh["worst_band_rate"] - stale["worst_band_rate"]) < 0.05, \
        "if recalibration moved the subgroup rate much, G3 is overstated"

    assert pct(fresh["worst_band_rate"]) in readme
    assert f"{fresh['max_concentration']:.2f}" in readme


def test_the_coverage_advantage_shrinks_but_survives(readme, recal):
    """
    G2. Most of the stale advantage was staleness, and the write-up says the
    smaller number rather than the larger one.
    """
    def cov(label: str, scheme: str, share: float) -> float:
        return rpoint(recal, label, scheme, share)["mean_coverage"]

    stale_gap = cov("stale", "by-band", 1.00) - cov("stale", "pooled", 1.00)
    fresh_gap = cov("recalibrated", "by-band", 0.143) - \
        cov("recalibrated", "pooled", 0.143)
    assert stale_gap > 0.30
    assert 0.0 < fresh_gap < 0.10
    assert pct(fresh_gap) in readme or f"+{fresh_gap * 100:.1f}" in readme


def test_the_two_schemes_coincide_when_there_is_one_group(recal):
    """
    A sanity check that would catch a bug in the grouping itself: at a 100%
    share there is one band, so by-band and pooled must agree exactly.
    """
    a = rpoint(recal, "recalibrated", "pooled", 1.00)["mean_coverage"]
    b = rpoint(recal, "recalibrated", "by-band", 1.00)["mean_coverage"]
    assert a == pytest.approx(b, abs=1e-9)


def test_an_all_infeasible_point_is_not_reported_as_zero_coverage(readme,
                                                                  recal):
    """
    At an 80% share group conditioning never certifies. Reporting that as 0%
    coverage would read as "resolved nothing" when it means "never
    certified" — different outcomes with opposite implications.
    """
    p = rpoint(recal, "recalibrated", "by-band", 0.80)
    assert p["feasible_trials"] == 0
    assert "never certified" in readme


# ---------------------------------------------------------------------------
# Does the mechanism survive a learned scorer?
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fitted_cond():
    p = ROOT / "evidence" / "fitted_conditional.json"
    if not p.exists():
        pytest.skip("the fitted-scorer run has not happened")
    return json.loads(p.read_text())


def arm(payload: dict, scorer: str, alpha: float) -> dict:
    """
    One arm's breakdown, skipping cleanly when the run predates it.

    The evidence file grew a third arm after the first two were already
    committed, so a checkout carrying the older file should skip rather than
    raise — an absent arm is "not measured here", not a failure.
    """
    if scorer not in payload:
        pytest.skip(f"this run predates the {scorer!r} arm")
    return next(r for r in payload[scorer] if r["alpha"] == alpha)


def test_a_learned_scorer_also_concentrates(readme, fitted_cond):
    """
    H1 and H2, which are what make the central finding more than a story
    about one hand-built feature.

    If a scorer that learns its weights did NOT concentrate, the mechanism
    would be a property of the handcrafted distance feature and the README's
    generalisation would have to come out.
    """
    for alpha in (0.20, 0.15):
        f = arm(fitted_cond, "fitted", alpha)
        assert f["hides_a_subgroup"] is True, alpha
        assert f["worst_band"] == "well-below", alpha
        assert f["concentration"][f["worst_band"]] > 2.0, alpha


def test_the_learned_scorer_is_genuinely_better_on_pooled_measures(
        readme, fitted_cond):
    """
    Otherwise "it concentrates even though it is better" is not established —
    it might simply be a worse scorer failing in a familiar way.
    """
    hand = arm(fitted_cond, "handcrafted", 0.20)
    fit = arm(fitted_cond, "fitted", 0.20)
    assert fit["mean_coverage"] > hand["mean_coverage"] + 0.05
    assert pct(fit["mean_coverage"]) in readme
    assert pct(hand["mean_coverage"]) in readme


def test_h3_is_recorded_as_a_miss(readme, fitted_cond):
    """
    It predicted the fitted scorer's pooled rate would be at or below the
    handcrafted one's. It is higher at both tolerances.
    """
    worse_somewhere = any(
        arm(fitted_cond, "fitted", a)["pooled_unsafe_rate"] >
        arm(fitted_cond, "handcrafted", a)["pooled_unsafe_rate"]
        for a in (0.20, 0.15))
    assert worse_somewhere, "H3 now holds; the write-up must stop calling it a miss"
    assert "**H3** missed" in (ROOT / "README.md").read_text() or \
        "H3 missed" in (ROOT / "README.md").read_text()


def test_the_worst_band_rates_quoted_are_the_measured_ones(readme,
                                                           fitted_cond):
    for scorer in ("handcrafted", "fitted"):
        d = arm(fitted_cond, scorer, 0.20)
        row = next(b for b in d["bands"] if b["band"] == d["worst_band"])
        assert pct(row["unsafe_rate"]) in readme, scorer
        assert f"{d['concentration'][d['worst_band']]:.2f}" in readme, scorer


def test_the_strong_claim_is_reported_as_refuted(readme, fitted_cond):
    """
    J1 failed, and the README must say so rather than quietly narrowing.

    I claimed the concentration was a property of using one threshold rather
    than of the score's features, and pre-registered that a no-distance
    scorer failing to concentrate would refute it. It does fail to
    concentrate — 1.72x, every band inside budget — so the claim is narrowed
    in the text and the refutation is named.
    """
    blind = arm(fitted_cond, "fitted-no-distance", 0.20)
    hand = arm(fitted_cond, "handcrafted", 0.20)

    assert blind["hides_a_subgroup"] is False
    blind_conc = blind["concentration"][blind["worst_band"]]
    hand_conc = hand["concentration"][hand["worst_band"]]
    assert blind_conc < hand_conc / 2, (blind_conc, hand_conc)

    text = (ROOT / "README.md").read_text()
    assert "strong claim is refuted" in text
    assert f"{blind_conc:.2f}" in readme
    # And the narrowed claim must still be stated, not merely withdrawn.
    assert "does **not** vanish" in text


def test_the_worst_auc_scorer_wins_on_both_deployed_axes(readme,
                                                         fitted_cond):
    """
    The fourth AUC result, and the only one pointing backwards.

    If a future run reverses this, the README's "worst AUC, best on both
    axes" sentence is wrong and must change.
    """
    arms = {a: arm(fitted_cond, a, 0.20)
            for a in ("handcrafted", "fitted", "fitted-no-distance")}
    worst_auc = min(arms.values(), key=lambda d: d["auc"])

    assert worst_auc["scorer"] == "fitted-no-distance"
    assert all(worst_auc["pooled_unsafe_rate"] <= d["pooled_unsafe_rate"]
               for d in arms.values())
    assert all(worst_auc["mean_coverage"] >= d["mean_coverage"]
               for d in arms.values())
    assert f"{worst_auc['auc']:.4f}" in readme
    # The count is derived in tests/test_preregistration.py from the README's
    # own numbered list; asserting the word here is what let it go stale.
    assert "independent results here saying AUC cannot see" in readme


def test_j3_and_j4_are_recorded_as_misses(readme, fitted_cond):
    blind = arm(fitted_cond, "fitted-no-distance", 0.20)
    assert blind["mean_coverage"] > 0.60, "J3 predicted under 60%"
    assert blind["auc"] > 0.80, "J4 predicted under 0.80"
    text = (ROOT / "README.md").read_text()
    assert "J1, J3 and J4 all missed" in text


def test_conditioning_fixes_the_learned_scorer_too(readme, fitted_cond):
    """
    H4, which the first version of the experiment never actually measured.

    `validate_groups` had no refit, so that arm passed the handcrafted scorer
    to every row and printed a duplicate of an earlier result. This asserts
    the fitted arm exists and that conditioning helps it on both axes.
    """
    rows = [r for r in fitted_cond.get("schemes", [])
            if r.get("scorer") == "fitted" and r["alpha"] == 0.20]
    if not rows:
        pytest.skip("this run predates the fitted scheme arm")

    pooled = next(r for r in rows if r["scheme"] == "pooled")
    band = next(r for r in rows if r["scheme"] == "by-band")

    assert band["group_violation_rate_when_feasible"] < \
        pooled["group_violation_rate_when_feasible"] / 5
    assert band["mean_worst_group_rate"] < pooled["mean_worst_group_rate"] / 2
    assert band["mean_coverage"] > pooled["mean_coverage"], \
        "the Pareto improvement has to hold for the learned scorer as well"

    for value in (pct(pooled["group_violation_rate_when_feasible"]),
                  pct(band["group_violation_rate_when_feasible"]),
                  pct(band["mean_worst_group_rate"]),
                  pct(band["mean_coverage"])):
        assert value in readme, value


def test_both_scorers_appear_in_the_scheme_arm(fitted_cond):
    """
    The guard against the bug that made H4 meaningless: if only one scorer
    is present, the arm is comparing a scorer with itself again.
    """
    rows = fitted_cond.get("schemes", [])
    if not rows:
        pytest.skip("no scheme arm in this run")
    assert {r.get("scorer") for r in rows} == {"handcrafted", "fitted"}


# ---------------------------------------------------------------------------
# Uncertainty, at the unit the data has
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def uncertainty():
    p = ROOT / "evidence" / "uncertainty.json"
    if not p.exists():
        pytest.skip("the uncertainty run has not happened")
    return json.loads(p.read_text())["rows"]


def cell(rows: list[dict], which: str, alpha: float, band: str) -> dict:
    return next(r for r in rows if r["set"] == which
                and r["alpha"] == alpha and r["band"] == band)


def test_the_finding_survives_honest_error_bars(uncertainty):
    """
    The check that decides whether the headline stands.

    If the cluster-bootstrap lower bound dipped below the tolerance, the
    subgroup result would be "possibly over budget" rather than "over
    budget", and the README would have to say so.
    """
    for which in ("dev", "holdout"):
        for alpha in (0.20, 0.15):
            c = cell(uncertainty, which, alpha, "well-below")
            assert c["lo"] > alpha, (which, alpha, c["lo"])


def test_the_clustered_interval_is_much_wider_than_the_naive_one(
        readme, uncertainty):
    """
    The methodological point. If these ever converged, the clustering would
    have stopped mattering and the section explaining it would be wrong.
    """
    c = cell(uncertainty, "holdout", 0.20, "well-below")
    assert c["clustered_halfwidth"] > 10 * c["naive_halfwidth"]
    assert c["observations"] > 100 * c["cases"], \
        "the whole point is that observations vastly outnumber cases"

    assert pct(c["lo"]) in readme and pct(c["hi"]) in readme
    assert str(c["cases"]) in readme


def test_the_readme_quotes_the_bootstrap_not_the_naive_interval(readme,
                                                                uncertainty):
    c = cell(uncertainty, "holdout", 0.20, "well-below")
    assert pct(c["clustered_halfwidth"]) in readme
    text = " ".join((ROOT / "README.md").read_text().split())
    assert "resampling **cases**" in text.lower() or \
        "Resampling **cases**" in text


def test_the_bootstrap_point_matches_the_published_run(uncertainty, round4,
                                                       holdout):
    """
    A confidence interval around a different point estimate would be
    describing a different experiment. The runner asserts this too; this
    pins it in the committed evidence.
    """
    for which, payload in (("dev", round4), ("holdout", holdout)):
        ref = next(c for c in payload["E3_E8_concentration"]
                   if c["alpha"] == 0.20)
        for band in ("well-below", "near-threshold", "above", "well-above"):
            was = next(b["unsafe_rate"] for b in ref["bands"]
                       if b["band"] == band)
            now = cell(uncertainty, which, 0.20, band)["point"]
            assert was == pytest.approx(now, abs=1e-9), (which, band)


# ---------------------------------------------------------------------------
# Does the method's own justification survive at scale?
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def plugin_scale():
    p = ROOT / "evidence" / "plugin_scale.json"
    if not p.exists():
        pytest.skip("the plug-in scale sweep has not been run")
    return json.loads(p.read_text())


def at_size(payload: dict, alpha: float, n_cal: int, bound: str) -> dict:
    return next(r for r in payload["rows"] if r["alpha"] == alpha
                and r["calibration_size"] == n_cal and r["bound"] == bound)


def test_the_correction_matters_at_every_size_tested(readme, plugin_scale):
    """
    K2's refutation, which is what the README's baseline section now rests
    on. If a future run shows the plug-in holding delta at the largest fold,
    the section's claim is wrong and must be narrowed to "below some n".
    """
    delta = plugin_scale["delta"]
    for alpha in (0.20, 0.10):
        for n_cal in plugin_scale["sizes"]:
            plug = at_size(plugin_scale, alpha, n_cal, "plugin")
            rate = plug["violation_rate_when_feasible"]
            assert rate is not None and rate > delta, (alpha, n_cal, rate)


def test_the_conformal_rule_holds_delta_at_every_size(plugin_scale):
    """K4. Where it cannot, it must decline rather than offer a threshold."""
    for alpha in (0.20, 0.10):
        for n_cal in plugin_scale["sizes"]:
            c = at_size(plugin_scale, alpha, n_cal, "clopper-pearson")
            if c["feasible_trials"] == 0:
                assert c["infeasible_rate"] == 1.0, (alpha, n_cal)
                continue
            assert c["holds"] is True, (alpha, n_cal)


def test_only_one_arm_ever_declines(plugin_scale):
    """
    The asymmetry the section turns on: the plug-in always has a threshold
    to offer, and the threshold is not safe.
    """
    for alpha in (0.20, 0.10):
        for n_cal in plugin_scale["sizes"]:
            assert at_size(plugin_scale, alpha, n_cal,
                           "plugin")["infeasible_rate"] == 0.0


def test_k1_is_recorded_as_a_miss(readme, plugin_scale):
    """
    I predicted the plug-in's violation rate would fall monotonically with
    calibration size. At alpha = 0.20 it rises again at the largest fold.
    """
    rates = [at_size(plugin_scale, 0.20, n, "plugin")
             ["violation_rate_when_feasible"]
             for n in plugin_scale["sizes"]]
    assert rates != sorted(rates, reverse=True), \
        "K1 now holds; the write-up must stop calling it a miss"
    assert "K1 and K2 both missed" in (ROOT / "README.md").read_text()


def test_the_quoted_scale_table_is_the_measured_one(readme, plugin_scale):
    for alpha in (0.20, 0.10):
        for n_cal in plugin_scale["sizes"]:
            for bound in ("clopper-pearson", "plugin"):
                r = at_size(plugin_scale, alpha, n_cal, bound)
                v = r["violation_rate_when_feasible"]
                if v is None:
                    continue
                assert pct(v) in readme, (alpha, n_cal, bound, v)


# ---------------------------------------------------------------------------
# The fifth AUC result: three scorers, one policy
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def signed():
    p = ROOT / "evidence" / "signed_scorer.json"
    if not p.exists():
        pytest.skip("signed_scorer.json not present")
    return json.loads(p.read_text())


@pytest.fixture(scope="module")
def opening():
    p = ROOT / "evidence" / "opening_state.json"
    if not p.exists():
        pytest.skip("opening_state.json not present")
    return json.loads(p.read_text())


def test_the_identical_policy_table_is_the_measured_one(readme, signed):
    """
    Every figure in the README's one-policy table, at the precision it uses.

    The claim is that three scorers produce the same deployed behaviour. A
    table of twenty-four numbers asserting it is only worth having if the
    numbers are the measured ones, so each is checked against the run at two
    decimal places — which is the precision the README prints, chosen
    because one decimal cannot distinguish 11.29% from 11.31%.
    """
    text = " ".join((ROOT / "README.md").read_text().split())
    row = next(r for r in signed["arms"]["signed"] if r["alpha"] == 0.20)

    for form in pct_forms(row["pooled_unsafe_rate"], places=2):
        if form in text:
            break
    else:
        pytest.fail(f"pooled {row['pooled_unsafe_rate']:.2%} not in the README")

    for band in row["bands"]:
        assert any(f in text for f in pct_forms(band["unsafe_rate"], 2)), \
            (band["band"], band["unsafe_rate"])

    assert any(f in text for f in pct_forms(row["mean_coverage"], 2)), \
        row["mean_coverage"]
    assert f"{row['mean_questions']:.4f}" in text, row["mean_questions"]
    worst = row["concentration"][row["worst_band"]]
    assert f"{worst:.4f}" in text, worst


def test_the_three_aucs_are_the_measured_ones(readme, signed):
    """
    The point of the section is that these three differ. If they drift to
    equal, the section is making a claim its own evidence contradicts.
    """
    text = " ".join((ROOT / "README.md").read_text().split())
    aucs = {k: v[0]["auc"] for k, v in signed["arms"].items()}
    assert len(set(aucs.values())) == 3, aucs
    for label, a in aucs.items():
        assert f"{a:.4f}" in text, (label, a)

    spread = max(aucs.values()) - min(aucs.values())
    assert f"{spread:.4f}" in text, \
        f"the README quotes the AUC spread; measured {spread:.4f}"


def test_the_opening_state_figures_in_the_readme_are_measured(readme,
                                                              opening):
    """
    The mechanism's numbers: who asks first, and who commits immediately.
    """
    text = " ".join((ROOT / "README.md").read_text().split())
    hand = opening["first_question"]["handcrafted"]
    assert has_count(text, hand["n_asking"]), hand["n_asking"]

    commits = opening["immediate_commits"]
    assert has_count(text, commits["handcrafted"]), commits
    assert has_count(text, commits["signed"]), commits
    assert commits["award-aware"] == 0, commits

    for label in ("award-aware", "signed"):
        rate = opening["order_flips"][label]["flip_rate"]
        assert any(f in text for f in pct_forms(rate, 2)), (label, rate)


def test_the_group_conditional_arms_quoted_are_the_measured_ones(readme,
                                                                 signed):
    """
    The parenthetical claiming the group-conditional arms are identical too.
    """
    text = " ".join((ROOT / "README.md").read_text().split())
    at20 = [s for s in signed["schemes"] if s["alpha"] == 0.20]
    pooled = next(s for s in at20 if s["scheme"] == "pooled"
                  and s["scorer"] == "signed")
    byband = next(s for s in at20 if s["scheme"] == "by-band"
                  and s["scorer"] == "signed")

    for s in (pooled, byband):
        gv = s["group_violation_rate_when_feasible"]
        assert any(f in text for f in pct_forms(gv, 2) + pct_forms(gv, 1)), gv
        w = s["mean_worst_group_rate"]
        assert any(f in text for f in pct_forms(w, 2)), (s["scheme"], w)
    assert has_count(text, byband["feasible_trials"]), \
        byband["feasible_trials"]


def test_the_vacuous_holds_are_called_vacuous_in_the_readme(readme):
    """
    Four of nine predictions held because the arm was a no-op. The README
    must not report that as four passes.
    """
    text = " ".join((ROOT / "README.md").read_text().split())
    assert "vacuously" in text, \
        "a cost prediction satisfied by a no-op has to be labelled"
    assert "five missed" in text


def test_the_readme_counts_theory_claims_from_theory(readme):
    """
    The README summarises `theory.md` and said "Three claims" while listing
    four bullets and theory.md carried four numbered sections.

    Derived from theory.md's own section headings, so adding a fifth claim
    there fails here until the README agrees — and so does the count in
    theory.md's own opening line, which is the other place it is typed.
    """
    text = (ROOT / "docs" / "theory.md").read_text()
    n = len(re.findall(r"^## \d+\. ", text, re.M))
    assert n >= 4, n

    words = ("zero one two three four five six seven eight").split()
    assert f"{words[n]} claims resting" in readme.lower(), n
    assert f"{words[n]} claims appear in this repository" in \
        " ".join(text.split()).lower(), n

    # Scoped to "<n> claims RESTING", which is the phrase that states this
    # count. The first version forbade any "<n> claims" anywhere in the
    # README and promptly failed on "two claims published here and then
    # retracted" -- a count of something else entirely. Second time a guard
    # in this suite has been too broad rather than too narrow; both times
    # the symptom was a false failure on correct prose, which is the benign
    # direction but still a guard nobody can trust.
    for other in words:
        if other == words[n]:
            continue
        bad = re.compile(rf"(?<![\w-]){other} claims resting", re.I)
        assert not bad.search(readme), (other, n)


# ---------------------------------------------------------------------------
# Round Q: the partition the finding is phrased in
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sweep():
    p = ROOT / "evidence" / "partition_sweep.json"
    if not p.exists():
        pytest.skip("the partition sweep has not been run in this checkout")
    return json.loads(p.read_text())


def worst_of(row: dict) -> tuple[str, float, float]:
    w = row["worst_band"]
    rate = next((b["unsafe_rate"] for b in row["bands"]
                 if b["band"] == w), 0.0)
    return w, rate, row["concentration"].get(w, 0.0)


def test_the_control_partition_reproduces_the_published_breakdown(sweep,
                                                                  round4):
    """
    The sweep's own control, which makes the rest of it a comparison.

    `published` in the sweep is a reimplementation of `hardness` as a
    cutoff list. If it disagreed with the breakdown every other result in
    the repository uses, the eight other partitions would be measured
    against the wrong baseline and the whole round would be noise.

    Pinned against round four's figure rather than against the sweep's own
    other arms, so this cannot pass by being self-consistently wrong.
    """
    pub = sweep["by_alpha"]["0.20"]["published"]
    w, rate, conc = worst_of(pub)
    assert w == "well-below", w

    # bottom-at-6k is the same grouping under a different band name, so the
    # two must agree to every digit -- an internal check the round gets free.
    same = sweep["by_alpha"]["0.20"]["bottom-at-6k"]
    assert worst_of(same)[1] == rate
    assert worst_of(same)[2] == conc

    ref = next(r for r in round4["E1_E3_dev"] if r["alpha"] == 0.20) \
        if "E1_E3_dev" in round4 else None
    if ref is not None:
        assert abs(ref["concentration"]["well-below"] - conc) < 0.05, \
            (ref["concentration"]["well-below"], conc)


def test_the_finding_survives_a_neutral_partition(readme, sweep):
    """
    Q1 to Q3, and the claim the section rests on.

    Equal-count quartiles are chosen from the income distribution with no
    reference to any result. If the poorest quartile were inside budget, the
    subgroup finding would be a property of three constants in `split.py`
    and the README would have to say so at the top.
    """
    neutral = sweep["by_alpha"]["0.20"]["equal-count-quartiles"]
    w, rate, conc = worst_of(neutral)

    assert neutral["hides_a_subgroup"] is True, "Q1"
    assert w == "q1-poorest", ("Q2", w)
    assert rate > 0.20, ("the quartile must exceed the budget", rate)
    assert conc > 2.0, ("Q3", conc)

    assert any(f in readme for f in pct_forms(rate, 1)), rate
    assert f"{conc:.2f}" in readme, conc


def test_the_readme_reports_the_tolerance_limit_it_found(readme, sweep):
    """
    The unpredicted result that cuts against the finding.

    At α = 0.15 the neutral partition's poorest quartile lands inside the
    budget, by less than half a point. Omitting that would make the sweep
    read as a clean confirmation, which it is not, so the figure has to
    appear and the word has to be there.
    """
    at15 = sweep["by_alpha"]["0.15"]["equal-count-quartiles"]
    _, rate, _ = worst_of(at15)
    assert at15["hides_a_subgroup"] is False, \
        "this test exists because the neutral partition misses at 0.15"
    assert rate < 0.15, rate

    assert any(f in readme for f in pct_forms(rate, 2)), rate
    assert "tolerance-sensitive" in readme, \
        "a limit found and not named is a limit not reported"


def test_a_coarse_partition_hides_the_finding(readme, sweep):
    """
    The most actionable thing the round produced, and it was not predicted.

    Two bands at the median report no hidden subgroup at either tolerance.
    An operator checking with two groups concludes there is nothing there.
    """
    for alpha in ("0.20", "0.15"):
        two = sweep["by_alpha"][alpha]["two-bands-at-median"]
        assert two["hides_a_subgroup"] is False, alpha
        assert len(two["bands"]) == 2, two["bands"]

    _, rate, conc = worst_of(sweep["by_alpha"]["0.20"]["two-bands-at-median"])
    assert conc < 2.0, conc
    assert f"{conc:.2f}" in readme, conc
    assert any(f in readme for f in pct_forms(rate, 1)), rate


def test_the_effect_concentrates_toward_the_bottom_of_the_range(readme,
                                                                sweep):
    """
    Q4 and Q5 together: the concentration is monotone in the bottom cutoff
    and highest at the narrowest band.

    Monotone-and-falling alone would be explained by dilution. What makes it
    a statement about where the effect lives is that the narrowest cutoff
    exceeds the published one rather than matching it.
    """
    edges = (3, 6, 9, 12, 15)
    series = [worst_of(sweep["by_alpha"]["0.20"][f"bottom-at-{e}k"])[2]
              for e in edges]
    assert series == sorted(series, reverse=True), series
    assert series[0] > series[1], ("Q5", series[:2])

    for conc in (series[0], series[-1]):
        assert f"{conc:.2f}" in readme, conc


def test_every_partition_is_tallied_from_one_run(sweep):
    """
    The design property that makes this a partition comparison.

    All nine breakdowns come from one `validate` pass per tolerance, so
    their pooled rates, coverage and trial counts must be identical. If they
    differ, the collectors were not fanned out over shared trajectories and
    every difference between partitions is confounded with run-to-run noise.
    """
    for alpha, rows in sweep["by_alpha"].items():
        pooled = {r["pooled_unsafe_rate"] for r in rows.values()}
        cov = {r["mean_coverage"] for r in rows.values()}
        trials = {r["trials"] for r in rows.values()}
        assert len(pooled) == 1, (alpha, sorted(pooled))
        assert len(cov) == 1, (alpha, sorted(cov))
        assert len(trials) == 1, (alpha, sorted(trials))


# ---------------------------------------------------------------------------
# Round O: attacking the result that refuted the central claim
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ndg():
    p = ROOT / "evidence" / "no_distance_groups.json"
    if not p.exists():
        pytest.skip("round O has not been run in this checkout")
    return json.loads(p.read_text())


def nd_arm(payload: dict, alpha: float) -> dict:
    return next(r for r in payload["fitted-no-distance"]
                if r["alpha"] == alpha)


def nd_scheme(payload: dict, scorer: str, alpha: float, scheme: str) -> dict:
    return next(s for s in payload["schemes"]
                if s["scorer"] == scorer and s["alpha"] == alpha
                and s["scheme"] == scheme)


def test_round_o_reproduces_round_j_where_they_overlap(ndg, fitted_cond):
    """
    The pairing that makes round O an extension rather than a new experiment.

    Same seed, same share, same refit protocol, so the two tolerances round J
    measured must come back identical. If they do not, the alpha = 0.10 arm
    is not comparable to the published figures and the whole round is a
    separate run that happens to use the same scorer.
    """
    assert ndg["seed"] == fitted_cond["seed"], (ndg["seed"],
                                                fitted_cond["seed"])
    for alpha in (0.20, 0.15):
        o = nd_arm(ndg, alpha)
        j = arm(fitted_cond, "fitted-no-distance", alpha)
        assert o["pooled_unsafe_rate"] == pytest.approx(
            j["pooled_unsafe_rate"], abs=1e-12), alpha
        assert o["mean_coverage"] == pytest.approx(
            j["mean_coverage"], abs=1e-12), alpha
        assert o["auc"] == pytest.approx(j["auc"], abs=1e-12), alpha


def test_o1_missed_and_the_readme_says_the_rate_collapsed(readme, ndg):
    """
    O1 predicted the no-distance scorer would break a 10% budget. It does
    not — the worst band falls to 3.79% and coverage rises.
    """
    ten = nd_arm(ndg, 0.10)
    w = ten["worst_band"]
    rate = next(b["unsafe_rate"] for b in ten["bands"] if b["band"] == w)

    assert ten["hides_a_subgroup"] is False
    assert rate < 0.10, rate
    assert any(f in readme for f in pct_forms(rate, 2)), rate
    assert any(f in readme for f in pct_forms(ten["mean_coverage"], 2)), \
        ten["mean_coverage"]


def test_the_two_estimators_are_both_reported(readme, ndg):
    """
    The correction round O produced, and the one most worth a guard.

    The README said removing the feature "brings every band inside the
    budget". That is the across-trial estimator. On the per-trial one, a
    quarter of deployments put a band over budget at the two tighter
    tolerances. Both numbers have to be in the write-up or the sentence
    reads as a clean result again.
    """
    for alpha in (0.20, 0.15, 0.10):
        pooled = nd_scheme(ndg, "fitted-no-distance", alpha, "pooled")
        gv = pooled["group_violation_rate_when_feasible"]
        assert any(f in readme for f in pct_forms(gv, 1)), (alpha, gv)

    tight = nd_scheme(ndg, "fitted-no-distance", 0.15, "pooled")
    assert tight["group_violation_rate_when_feasible"] > 0.20, \
        "this guard exists because the per-trial rate is large at 0.15"

    text = " ".join((ROOT / "README.md").read_text().split())
    assert "on this estimator" in text, \
        "the qualified version of the refuted sentence has to be the one " \
        "in the write-up"


def test_no_remedy_is_available_at_the_tightest_tolerance(readme, ndg):
    """
    O3's miss, which is the finding with a consequence for practice.

    Group conditioning is infeasible in every trial at alpha = 0.10, for
    both scorers. A reader who takes "condition per group" as the answer
    needs to know the answer is unavailable there.
    """
    nd = nd_scheme(ndg, "fitted-no-distance", 0.10, "by-band")
    hand = nd_scheme(ndg, "handcrafted", 0.10, "by-band")
    assert nd["feasible_trials"] == 0, nd["feasible_trials"]
    assert hand["feasible_trials"] < 10, hand["feasible_trials"]

    assert has_count(readme, nd["feasible_trials"]) or "0/200" in readme
    assert has_count(readme, hand["feasible_trials"]), \
        hand["feasible_trials"]
    assert "no remedy" in readme.lower(), \
        "the unavailability has to be stated, not left in a table"


def test_the_cost_of_tightening_is_questions_not_coverage(readme, ndg):
    """
    The secondary finding: with this scorer, coverage RISES as the tolerance
    tightens and the cost shows up in questions per case.

    Worth a guard because the whole write-up frames the trade as safety
    against coverage, and here that framing is wrong.
    """
    rows = [nd_arm(ndg, a) for a in (0.20, 0.15, 0.10)]
    qs = [r["mean_questions"] for r in rows]
    covs = [r["mean_coverage"] for r in rows]
    assert qs == sorted(qs), qs
    assert covs == sorted(covs), covs

    for q in (qs[0], qs[-1]):
        assert f"{q:.2f}" in readme, q


def test_conditioning_and_feature_removal_are_complements(ndg):
    """
    The claim that replaced "removing it beat every alternative".

    Where both are feasible, the combination must be safer on the per-trial
    measure than either alone. If it is not, "complements rather than
    substitutes" is wrong and the recommendation has to change back.
    """
    for alpha in (0.20, 0.15):
        both = nd_scheme(ndg, "fitted-no-distance", alpha, "by-band")
        feature_only = nd_scheme(ndg, "fitted-no-distance", alpha, "pooled")
        cond_only = nd_scheme(ndg, "handcrafted", alpha, "by-band")
        assert both["feasible_trials"] > 0, alpha
        gv = both["group_violation_rate_when_feasible"]
        assert gv <= feature_only["group_violation_rate_when_feasible"], alpha
        assert gv <= cond_only["group_violation_rate_when_feasible"], alpha


def test_the_per_trial_intervals_in_the_readme_are_the_computed_ones(readme,
                                                                    ndg):
    """
    Six cells, each an exact interval derived from the run's own k and n.

    Two of them mislead without an interval and that is why this exists: 2.6%
    on 196 trials beside 2.5% on 200 reads as conditioning narrowly losing
    when the intervals are indistinguishable, and 0.0% on 3 trials reads as
    a perfect result when its upper bound is 70.8%.

    Computed from the library function rather than retyped, so a change to
    the interval, the rates, or the feasible counts fails here.
    """
    from abstain.group import trial_rate_interval

    cells = [("handcrafted", "by-band"), ("fitted-no-distance", "pooled"),
             ("fitted-no-distance", "by-band")]
    checked = 0
    for alpha in (0.20, 0.15, 0.10):
        for scorer, scheme in cells:
            s = nd_scheme(ndg, scorer, alpha, scheme)
            n = s["feasible_trials"]
            gv = s["group_violation_rate_when_feasible"]
            if n == 0 or gv is None:
                continue
            lo, hi = trial_rate_interval(round(gv * n), n)
            assert f"[{lo * 100:.1f}, {hi * 100:.1f}]" in readme, \
                (scorer, alpha, scheme, lo, hi)
            checked += 1
    assert checked >= 6, checked


def test_the_three_trial_cell_carries_its_upper_bound(readme, ndg):
    """
    The single most misleading number in the round, pinned on its own.

    Zero failures in three trials is not evidence of safety, so the bound
    has to be *explained in prose* and not only sit in a table cell where a
    reader skims past it. The companion test above checks the cell; this one
    checks the sentence.

    The first version of this assertion did not do that. It looked for the
    figure anywhere in the README and for either of two phrases, and the
    figure appears in the table cell while one phrase appears elsewhere — so
    deleting the whole explanatory sentence left it passing, and its
    docstring claimed otherwise. A test whose docstring overstates what it
    checks is the same defect as prose overstating its evidence, so it is
    now scoped to the sentence itself and verified against its removal.
    """
    from abstain.group import trial_rate_interval

    s = nd_scheme(ndg, "handcrafted", 0.10, "by-band")
    n = s["feasible_trials"]
    assert n < 10, ("this test assumes the cell stayed underpowered", n)

    _, hi = trial_rate_interval(0, n)
    assert hi > 0.5, hi

    words = "zero one two three four five six seven eight nine".split()
    text = " ".join((ROOT / "README.md").read_text().split())
    sentence = (f"zero failures in **{words[n]}** feasible trials, upper "
                f"bound **{hi * 100:.1f}%**")
    assert sentence in text, sentence
    assert "supports almost nothing" in text, \
        "the bound has to be interpreted, not just printed"


def test_the_readme_says_what_the_trial_intervals_do_not_cover(readme):
    """
    They are conditional on the 672-case pool, and narrower than what an
    operator faces. Stating only the interval would be the same overclaim
    as the naive binomial interval this repository already rejected once.
    """
    assert "narrower than" in readme
    assert "Monte Carlo" in readme


# ---------------------------------------------------------------------------
# Round R: pool-level uncertainty for the headline per-trial rate
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pool_boot():
    p = ROOT / "evidence" / "pool_bootstrap.json"
    if not p.exists():
        pytest.skip("the pool bootstrap has not been run in this checkout")
    return json.loads(p.read_text())


def test_the_pool_level_intervals_quoted_are_the_measured_ones(readme, theory,
                                                               pool_boot):
    """
    Both arms, both intervals, in both documents.

    The README and theory.md carry the same four-cell table, so a figure
    that moves has to move in both or they disagree — which is exactly how
    theory.md came to carry a claim the README had already retracted.
    """
    for scheme in ("pooled", "by-band"):
        v = pool_boot["summary"][scheme]
        for payload in (readme, theory):
            assert any(f in payload
                       for f in pct_forms(v["mean"], 1)), (scheme, v["mean"])
            for bound in v["pool_interval"] + v["exact_interval"]:
                assert any(f in payload for f in pct_forms(bound, 1)), \
                    (scheme, bound)


def test_the_widening_ratio_is_the_headline_and_it_is_small(readme, theory,
                                                            pool_boot):
    """
    The result of the round: resampling cases widens these intervals by
    about a tenth, against sixteenfold for the per-band rates.

    Both ratios have to be in the write-up. Quoting only the small one
    would read as a licence to use narrow intervals everywhere, which is
    the opposite of what the comparison supports.
    """
    ratios = [pool_boot["summary"][s]["pool_width"]
              / pool_boot["summary"][s]["exact_width"]
              for s in ("pooled", "by-band")]
    for r in ratios:
        assert 1.0 < r < 1.3, r
        assert f"{r:.2f}" in readme, r

    # Scoped to the sentence that draws the contrast, not to the word
    # appearing anywhere. The first version checked `"sixteen" in payload`
    # and passed after the contrast was deleted, because the word also
    # appears two sections earlier about the band rates — the third
    # too-broad guard in this suite, and the only one that failed in the
    # dangerous direction: it would have let the write-up quote the small
    # ratio alone, which reads as a licence to use narrow intervals
    # everywhere and is the opposite of what the comparison supports.
    # Scoped to the section that draws the contrast, by heading, rather than
    # to the word appearing anywhere in the file. Two weaker versions of
    # this assertion passed after the contrast was deleted -- first because
    # "sixteen" appears two sections earlier about the band rates, then
    # because "sixteenfold" appears twice within this one. Third too-broad
    # guard in this suite and the only one that failed in the dangerous
    # direction: it would have let the write-up quote the small ratio alone,
    # which reads as a licence to use narrow intervals everywhere and is the
    # opposite of what the comparison supports.
    for name, head in (("README.md", "### The same treatment for the 98.2%"),
                       ("docs/theory.md",
                        "#### And the 98.2% carries its own width")):
        lines = (ROOT / name).read_text().splitlines()
        start = next(i for i, ln in enumerate(lines) if ln.startswith(head))
        depth = len(head) - len(head.lstrip("#"))
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("#")
                    and len(lines[i]) - len(lines[i].lstrip("#")) <= depth),
                   len(lines))
        section = " ".join(" ".join(lines[start:end]).split())

        assert "sixteenfold" in section, (
            name, "the per-band contrast has to sit inside this section")
        assert "whole pool" in section, (
            name, "and the mechanism, or the small ratio is a free pass")
        for r in ratios:
            assert f"{r:.2f}" in section, (name, r)


def test_round_r_predictions_all_held(pool_boot):
    """
    The only clean round in the ledger. If a re-run breaks one, the ledger
    is wrong and this says so before a reader finds it.
    """
    preds = pool_boot["predictions"]
    assert set(preds) == {"R1", "R2", "R3", "R4", "R5"}, sorted(preds)
    failed = [k for k, v in preds.items() if not v["held"]]
    assert not failed, failed


def test_the_arms_do_not_overlap_at_the_pool_level(pool_boot):
    """
    R3, and the most load-bearing comparison in the repository. If these
    intervals overlapped, every pooled-versus-conditioned table would need
    a width beside it and the recommendation would weaken to "measure it
    yourself".
    """
    p = pool_boot["summary"]["pooled"]["pool_interval"]
    g = pool_boot["summary"]["by-band"]["pool_interval"]
    assert g[1] < p[0], (g, p)


def test_group_feasibility_varies_across_resampled_pools(pool_boot):
    """
    R5, which is the design working rather than a finding.

    Group conditioning binds on the smallest group, so a resampled pool
    short in one band should be harder to certify. A constant feasible
    count would mean the bootstrap never reached what limits the method.
    """
    v = pool_boot["summary"]["by-band"]
    assert v["feasible_varies"] is True
    assert v["feasible_min"] < v["feasible_max"], v
    assert pool_boot["summary"]["pooled"]["feasible_min"] == \
        pool_boot["summary"]["pooled"]["feasible_max"], \
        "the pooled arm has one group and should always be feasible"


def test_the_interrupted_run_is_preserved_and_verified(readme):
    """
    The relaunch discipline, asserted rather than described.

    The interrupted log has to still be in the repository — it is the only
    thing that makes "the relaunch is the same draw" checkable — and the
    verifier has to actually agree.
    """
    import subprocess

    old = ROOT / "evidence" / "pool-bootstrap-interrupted.txt"
    new = ROOT / "evidence" / "pool-bootstrap-run.txt"
    if not (old.exists() and new.exists()):
        pytest.skip("the interrupted or completed log is not in this checkout")

    assert old.read_text().count("  draw ") >= 30, \
        "the interrupted log should hold the draws completed before the kill"

    out = subprocess.run([sys.executable,
                          str(ROOT / "scripts" / "verify_bootstrap_resume.py")],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "matches character for character" in out.stdout, out.stdout
    assert "verify_bootstrap_resume" in readme


# ---------------------------------------------------------------------------
# The contribution section: every figure in it, against its own evidence
# ---------------------------------------------------------------------------

def _contribution_section() -> str:
    lines = (ROOT / "README.md").read_text().splitlines()
    start = next(i for i, ln in enumerate(lines)
                 if ln.startswith("## What is new here"))
    end = next(i for i in range(start + 1, len(lines))
               if lines[i].startswith("## "))
    return " ".join(" ".join(lines[start:end]).split())


def test_the_contribution_section_names_the_prior_art(readme):
    """
    A section claiming what is new is only worth reading if it is explicit
    about what is not, and the prior art was named in four module docstrings
    and nowhere a reader would look first.
    """
    s = _contribution_section()
    for name in ("Clopper", "conformal", "Mondrian", "Vovk",
                 "cluster bootstrap", "Weighted conformal"):
        assert name in s, name
    assert "not presented as new" in s
    assert "not implemented" in s, \
        "weighted conformal is named as the right tool and absent; both halves"


def test_every_figure_in_the_contribution_section_is_measured(readme, round4,
                                                              ndg, sweep):
    """
    The section is a summary, which is where figures drift fastest — it is
    written once and the runs keep arriving.

    Each claim is checked against the evidence it summarises rather than
    against the body of the README, so a stale summary cannot be propped up
    by an equally stale section elsewhere.
    """
    s = _contribution_section()

    # The marginal/conditional pair, from round four.
    pooled = next(x for x in round4["E4_E7_schemes"]
                  if x["scheme"] == "pooled" and x["alpha"] == 0.20)
    overall = 1.0 - pooled["violation_rate_when_feasible"]
    conditional = pooled["group_violation_rate_when_feasible"]
    assert any(f in s for f in pct_forms(overall, 1)), overall
    assert any(f in s for f in pct_forms(conditional, 1)), conditional

    # Group conditioning is unavailable at the tight tolerance, from round O.
    tight = nd_scheme(ndg, "handcrafted", 0.10, "by-band")
    assert has_count(s, tight["feasible_trials"]), tight["feasible_trials"]

    # The AUC span, from round N.
    assert "0.9425" in s and "0.9604" in s

    # The neutral partition survives, from round Q.
    assert sweep["by_alpha"]["0.20"]["equal-count-quartiles"][
        "hides_a_subgroup"] is True
    assert "equal-count partition" in s or "equal-count" in s


def test_the_contribution_section_leads_with_the_limitation(readme):
    """
    "No model was run" has to be in this section, not only eleven hundred
    lines down. A summary of contributions that omits the governing
    limitation is the most natural place for this repository to overstate
    itself.
    """
    s = _contribution_section()
    assert "No model was run" in s
    assert "cannot\nanswer" in (ROOT / "README.md").read_text() or \
        "cannot answer" in s
    assert "substitute rather than an answer" in s


# ---------------------------------------------------------------------------
# Claim 2's evidence, which had no script and no test until it was wrong
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def unit_cmp():
    p = ROOT / "evidence" / "unit_comparison.json"
    if not p.exists():
        pytest.skip("unit_comparison.json not present")
    return json.loads(p.read_text())


def unit_row(payload: list[dict], unit: str, alpha: float) -> dict:
    return next(r for r in payload
                if r["unit"] == unit and r["alpha"] == alpha)


def test_the_unit_evidence_carries_the_feasibility_conditioned_metric(
        unit_cmp):
    """
    The field whose absence is the whole defect.

    The pre-correction files had `violation_rate` only, pooled over trials the
    procedure declined, so a 100%-infeasible arm reported 0% and read as a
    pass. Every row must now carry the conditioned metric, and it must be
    None rather than 0.0 where nothing was certified.
    """
    for r in unit_cmp:
        assert "violation_rate_when_feasible" in r, r
        assert "feasible_trials" in r, r
        if r["feasible_trials"] == 0:
            assert r["violation_rate_when_feasible"] is None, r
            assert r["holds"] is None, \
                "never certified is not held; `holds` must not be True"


def test_the_wrong_unit_manufactures_feasibility(readme, theory, unit_cmp):
    """
    The replacement claim, which is sharper than the retracted one.

    At the tight tolerance the state unit certifies and then violates in most
    of the trials it certified, while the trajectory unit declines in all of
    them. The difference is not a violation rate — it is that one unit issues
    a threshold it cannot honour.
    """
    state = unit_row(unit_cmp, "state", 0.05)
    traj = unit_row(unit_cmp, "trajectory", 0.05)

    assert state["feasible_trials"] > 0
    assert traj["feasible_trials"] == 0, traj
    assert state["violation_rate_when_feasible"] > 0.5, state

    for payload in (readme, theory):
        assert has_count(payload, state["feasible_trials"]), state
        assert any(f in payload for f in
                   pct_forms(state["violation_rate_when_feasible"], 1)), state
        assert "manufactures feasibility" in payload, \
            "the mechanism, not just the numbers"


def test_both_documents_retract_the_old_figures_rather_than_replacing_them(
        readme, theory):
    """
    "11% against 0%" was wrong in a way that flattered the method, and it sat
    inside a numbered claim. Replacing it quietly would be the one move this
    repository argues against throughout — and it would be the third time,
    which is why both documents have to say so and a test has to require it.
    """
    for name, payload in (("README.md", readme), ("docs/theory.md", theory)):
        low = payload.lower()
        assert "retracted" in low, name
        assert "11%" in payload, \
            (name, "the retracted figure stays visible as what was retracted")
        assert "76 were infeasible" in payload or \
            "**76 were infeasible**" in payload, name

    t = (ROOT / "docs" / "theory.md").read_text()
    assert "~~" in t, "theory.md strikes the old sentence through"


def test_the_orphaned_evidence_now_has_a_script(readme):
    """
    The deeper defect: no script wrote those two files, so they could not be
    regenerated, and no test read them, so nothing checked them.

    Every other evidence file in this repository is produced by a committed
    script. These two were the exception and it is the reason the error
    survived sixteen rounds.
    """
    script = ROOT / "scripts" / "rerun_unit_and_leakage.py"
    assert script.exists(), "claim 2's evidence needs a script like the rest"
    src = script.read_text()
    assert "violation_rate_when_feasible" in src
    assert "precorrection" in src, \
        "the pre-fix run is kept beside the fix, as everywhere else here"

    for name in ("unit_comparison-precorrection.json",
                 "leakage-precorrection.json"):
        assert (ROOT / "evidence" / name).exists(), name


def test_the_precorrection_files_show_the_defect_they_are_kept_for(unit_cmp):
    """
    The old files are only worth keeping if they still demonstrate the bug.
    If a future tidy-up regenerates them with the new metric, the record of
    what was wrong disappears.
    """
    p = ROOT / "evidence" / "unit_comparison-precorrection.json"
    if not p.exists():
        pytest.skip("pre-correction file not in this checkout")
    old = json.loads(p.read_text())

    vacuous = [r for r in old
               if r["infeasible_rate"] == 1.0 and r["violation_rate"] == 0.0]
    assert vacuous, "the kept file should still show the vacuous zero"
    assert all("violation_rate_when_feasible" not in r for r in old), \
        "the pre-correction file must stay pre-correction"
