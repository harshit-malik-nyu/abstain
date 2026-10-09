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


def test_the_rejected_hypothesis_is_still_rejected(mechanism):
    """
    The explanation I expected, pinned as rejected.

    If `well-below` were dominated by amount-only undeterminacy — clearly
    eligible households whose award still swings — the README's mechanism
    would be wrong. It is not dominated by it, and the band with the largest
    share of it takes none of the error budget.

    Asserted rather than narrated, so that a regenerated benchmark which
    *did* make the hypothesis true would fail here instead of leaving a wrong
    explanation standing.
    """
    crit = mechanism["criterion_split"]

    def amount_share(band: str) -> float:
        d = crit[band]
        return d["amount_only"] / (d["flip"] + d["amount_only"])

    assert amount_share("well-below") < 0.5, \
        "well-below would then be an amount-only story after all"
    assert amount_share("near-threshold") > amount_share("well-below"), \
        "the band taking none of the budget has the most amount-only states"


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


def test_eligibility_really_does_flip_for_the_failing_band(mechanism, readme):
    """
    Without this, "the scorer is wrong about them" has no content: the states
    could be undetermined for a reason the scorer is not claiming to see.
    """
    d = mechanism["criterion_split"]["well-below"]
    flip_share = d["flip"] / (d["flip"] + d["amount_only"])
    assert flip_share > 0.5
    assert f"{flip_share:.0%}" in readme


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
    assert "four independent results" in readme.lower()


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
