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
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def squash(path: str) -> str:
    """Whitespace-normalised, so line wrapping in the prose is irrelevant."""
    return " ".join((ROOT / path).read_text().split())


def pct(x: float, places: int = 1) -> str:
    return f"{x * 100:.{places}f}%"


@pytest.fixture(scope="module")
def readme():
    return squash("README.md")


@pytest.fixture(scope="module")
def theory():
    return squash("docs/theory.md")


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
