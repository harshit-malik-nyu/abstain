# Pre-registration, round five — breaking the assumption on purpose

Written before `src/abstain/shift.py` exists. The git history shows it.

---

## The gap this closes

Every guarantee in this repository rests on exchangeability: the deployed cases
are drawn like the calibration cases. `rule.py` says so, `validate.py` says it
cannot test it, `docs/theory.md` lists it as an assumption, and the README
points at a sibling project for what happens when it breaks.

**Nothing here measures it.** The project's central caveat is asserted and
never priced, which means a reader has no way to know whether the assumption
is a technicality or the whole ballgame.

It is cheap to measure, and the apparatus is already built. The income bands
partition the benchmark, round four established that the bands behave very
differently — `well-below` runs at 45.7% unsafe against a pooled 11.1% at
α = 0.20 — so **re-weighting the bands between calibration and deployment is a
realistic covariate shift with a known mechanism.** A benefits agency whose
applicant mix shifts toward the lowest-income band is not a hypothetical.

## The design

Calibrate on the natural band mix. Deploy on a mix where `well-below`'s share
is forced to **p**, sweeping p from its natural 14.3% to 100%. Everything else
— scorer, grid, δ, trials, the rule — is unchanged.

| | |
|---|---|
| **Set** | `evidence/fine_dev.json`, 672 cases |
| **Shift** | `well-below` share of the deployment fold ∈ {0.143, 0.25, 0.40, 0.60, 0.80, 1.00} |
| **Calibration** | natural mix, unshifted, every condition |
| **Schemes** | pooled · by-band |
| **α** | 0.20, 0.15 |
| **Trials** | 300 per condition |
| **Seed** | 41 |

Deployment folds are built by resampling the deployed cases to hit the target
share. That changes the deployment fold's size, so questions-per-case and
coverage are reported but the violation rate is the quantity of interest.

Calibration is held at the natural mix in every condition deliberately. The
operator does not know the shift is coming — that is what makes it a shift
rather than a different problem.

---

## Predictions

**F1.** At p = 0.143, the natural share, the pooled rule's violation rate will
be **at or below δ**. This is the control; if it fails, the resampling harness
is broken and nothing below means anything.

**F2.** The pooled rule's violation rate will **rise monotonically in p**.

**F3.** At p = 1.00 — deploying only on `well-below` — the pooled rule will
violate in **more than 80% of trials** at α = 0.20. The threshold was
calibrated for a mix where that band is 14.3% of cases, and the band's own
unsafe rate under that threshold is 45.7%, which is more than double the
tolerance.

**F4.** **Group-conditional calibration will be substantially robust to this
shift**: its violation rate at p = 1.00 will stay at or below δ, and in any
case below a fifth of the pooled rule's at the same p.

F4 is the prediction worth the round. Under group conditioning each band gets
its own threshold, so **re-weighting the bands changes which thresholds get
used and not what any threshold is.** The guarantee becomes invariant to shifts
in group proportions, because it was never a statement about the mixture in the
first place.

If F4 holds, two findings that looked separate are one finding:

> Group-conditional calibration is not only a fairness repair. It is the
> construction that makes the guarantee survive a shift in who shows up — and
> the subgroup that absorbs the budget is exactly the subgroup whose
> over-representation breaks the pooled rule.

That is a real reason to pay its costs, and it is stronger than "the pooled
number was misleading".

**F5.** The pooled rule's **reported bound will not move** as p rises. It is
computed on calibration data, which is unshifted, so the certificate stays
confident while the deployed rate degrades. A guarantee that fails silently is
worse than one that fails loudly, and this is the check on which this one does.

---

## What would falsify this round

- **F1 fails.** The harness is wrong. Nothing else is interpretable.
- **F4 fails.** Group conditioning does not buy shift robustness, the unifying
  claim above is withdrawn, and group conditioning goes back to being a
  fairness repair with a feasibility cost.

## What would not falsify it

- **F2 non-monotone at one step.** 300 trials and six shift levels; one
  inversion is noise, a reversal across the range is not.
- **F3 landing below 80%.** It is a magnitude guess about one band under one
  threshold.

## What this round does *not* establish

That the method is safe under distribution shift. It is not, and F3 is the
measurement of how unsafe.

What F4 would establish is narrower and worth stating precisely: the guarantee
is invariant to **shifts in the proportions of groups that were calibrated
separately.** It says nothing about a shift *within* a band, a new band that
calibration never saw, or a change in the relationship between the score and
determinability. Those break group conditioning exactly as they break the
pooled rule, and `group.threshold_for` already refuses to serve a group
calibration never saw rather than borrowing another group's threshold.

Conformal prediction under distribution shift has a literature — weighted
conformal methods for covariate shift, among others — and this round
implements none of it. It measures what the unweighted method costs when its
assumption is false, which is the thing a reader of this repository needs and
does not have.

## Analysis plan

One run on `fine_dev`, written to `evidence/round5_shift.json`. **The fine
holdout is not touched by this round** — round four's confirmatory run is the
only thing it carries.

No tuning. Misses reported as misses, pinned by test.

---

# Addendum — the objection round five invites

Written before `sweep_shift` grows a `shift_calibration` option. The git
history shows this commit precedes it.

## The objection

Round five holds calibration at the natural mix in every condition, on the
reasoning that an operator does not know a shift is coming. That is fair for
the *onset* of a shift and unfair afterwards, and it makes the comparison
vulnerable to a one-line rebuttal:

> Of course the pooled rule fails — you never let it recalibrate. A shifted
> population is a new population; recalibrate on it and the problem goes away.
> That is an operations question, not an argument for group conditioning.

If that rebuttal is right, the practical advice from this project collapses
from "calibrate per group, and here is what it costs" to "recalibrate when
your population moves", which is both easier and already standard practice.

The round-five numbers cannot answer it. The coverage advantage of group
conditioning *grows* with the shift — from +4.7 points at the natural mix to
**+38.4** at full shift — but that is measured against a pooled rule using a
threshold for a population that no longer exists, so it measures staleness
rather than conditioning.

## What is added

The same sweep with the **calibration fold reweighted to match the deployment
fold**. The operator now knows the mix and has recalibrated on it. Everything
else is unchanged.

| | |
|---|---|
| **Set** | `evidence/fine_dev.json` |
| **Shift** | as before, `well-below` share ∈ {0.143 … 1.00}, applied to **both** folds |
| **Trials** | 300 |
| **Seed** | 41, unchanged, so the two sweeps are paired per trial |

## Predictions

**G1.** With calibration shifted too, the pooled rule's violation rate will
return to **at or below δ at every shift level**. Recalibration fixes the
*validity* failure, and if it does not then round five was measuring something
other than staleness and its interpretation is wrong.

**G2.** Group conditioning will **still hold coverage at or above** the
recalibrated pooled rule at every shift level. Its advantage should shrink
substantially — most of the +38.4 points were staleness — but not vanish,
because within any mixture the bands still have shifted score distributions
and one threshold still cuts them at different quantiles.

**G3.** The recalibrated pooled rule will **still concentrate**: at the
natural mix its worst band will exceed α while its pooled rate does not.
Recalibration restores the marginal guarantee and does nothing for the
conditional one, because the thing it fixes is not the thing that was broken.

G3 is the one that matters. If it fails — if recalibrating also evens out the
budget — then the subgroup finding is a staleness artefact and the honest
recommendation is "recalibrate", not "condition".

## What would falsify the round-five interpretation

- **G1 fails.** Recalibration does not restore validity, so the shift result
  was not about staleness and needs re-explaining.
- **G3 fails.** The subgroup concentration is an artefact of a stale
  threshold rather than a property of one threshold, and the central finding
  of this repository is substantially weaker than stated. It would be
  reported that way, at the top of the README.

## What would not falsify it

**G2 shrinking to near zero.** If recalibration recovers most of the coverage,
that is a true and useful finding about what the fix is worth, and the
subgroup argument stands on G3 rather than on coverage.

---

# Addendum two — does a learned scorer concentrate too?

Written before any code reads `FittedScorer` through the conditional lens. The
git history shows it.

## Why this is the test the mechanism needs

The subgroup finding rests on one hand-built scorer whose only real feature is
distance from the eligibility boundary, and
[`scripts/diagnose_mechanism.py`](../scripts/diagnose_mechanism.py) traces the
failure to exactly that: the feature is maximal for households far *below* the
limit, where eligibility still flips 69% of the time. Stated that way it reads
as a defect of one feature, which would make the whole finding a story about a
toy scorer.

The claim I have actually been making is stronger and more general:

> The concentration is a property of using **one threshold** across groups
> whose score distributions sit at different levels, not a property of this
> score.

If that is right, a scorer that **learns** from labelled data — no hand-written
distance feature, weights fit by gradient descent — should concentrate too. If
it does not, my mechanism is wrong or is specific to the handcrafted feature,
and the README's generalisation has to come out.

`FittedScorer` is already in the repository and already has holdout results:
it beat the handcrafted scorer on coverage, 97.7% against 74.8%, at a nearly
identical AUC. **It has never been looked at per band.**

## The design

Identical to round four's concentration measurement, with the scorer swapped
and refit per trial on a fold disjoint from both calibration and deployment —
the three-fold protocol `validate.refit` already enforces, because a scorer fit
on the calibration or deployment data breaks the guarantee for reasons measured
earlier in this project.

| | |
|---|---|
| **Set** | `evidence/fine_dev.json` |
| **Scorers** | `handcrafted` (control) · `fitted`, refit per trial |
| **α** | 0.20, 0.15 |
| **Trials** | 200 |
| **Seed** | 53 |
| **Calibration share** | 0.30, as round four |

## Predictions

**H1.** The fitted scorer will **also concentrate**: at α = 0.20 some band's
share of unsafe commitments will exceed **2×** its share of deployments, and
`hides_a_subgroup` will be true.

**H2.** The worst band will be **the same band** — `well-below`. If the fitted
scorer fails on a *different* band, the concentration is general and its
location is scorer-specific, which is a weaker and still-reportable version of
the claim.

**H3.** The fitted scorer's **pooled** unsafe rate will be at or below the
handcrafted scorer's, consistent with its much higher coverage. It is a better
scorer by every pooled measure; that is the point of using it here.

**H4.** Group-conditional calibration will reduce its worst-band rate too, by
at least half. The fix should not care which scorer produced the levels.

## What would falsify the central mechanism

- **H1 fails.** A learned scorer does not concentrate, so the concentration is
  a property of the handcrafted distance feature rather than of single-threshold
  calibration. The README's generalisation comes out, the finding is restated
  as being about one scorer, and that is a materially weaker result which would
  be reported at the top rather than buried.

## What would not falsify it

- **H2 failing.** A different worst band would mean the *location* is
  scorer-specific while the phenomenon is not. Reportable as such.
- **H3 failing.** It would say the fitted scorer is worse on this axis, which
  is a fact about the scorer rather than about conditioning.

## Analysis plan

One run on `fine_dev`, written to `evidence/fitted_conditional.json`. Neither
holdout is touched. Misses reported as misses, pinned by test.

---

# Addendum three — a scorer that cannot see the boundary

Written before `FittedScorer.fit` grows an `exclude` parameter. The git
history shows it.

## The limit this closes

Addendum two showed a learned scorer concentrating on the same band at 3.31×.
That separates the finding from the handcrafted *functional form* — and not
from the *feature basis*, because `FittedScorer` learns weights over the same
features, `log_distance` among them. The write-up says so. This closes it.

Fit the same model with **`log_distance` and `income_known` removed**. What is
left is only which fields the agent knows: `n_unknown` and the four
`knows_*` indicators. Such a scorer cannot represent distance from the
eligibility boundary at all, so if the concentration were a property of that
feature it must disappear.

It will be a much weaker scorer, and that is the point. The question is not
whether it performs well; it is whether a single threshold over *any* score
spends its budget unevenly when the groups differ.

## Why it should still concentrate, if the mechanism is what I say

Without distance, the only signal is how many fields are missing — and the
bands differ sharply in how often a given knowledge state is undecidable:

| band | share of reachable states undetermined |
|---|---:|
| well-below | **76.6%** |
| near-threshold | 75.3% |
| above | 64.7% |
| well-above | **31.9%** |

A score that cannot tell the bands apart gets one threshold calibrated to the
pooled mixture, which is too permissive for the bands above the average and
too strict for those below it. That is the same mechanism arriving by a
different route: not "the feature is blind in one direction" but "the feature
cannot see the groups at all".

## Predictions

**J1.** The no-distance scorer will **still concentrate** — some band above
**2×** its share, `hides_a_subgroup` true, at α = 0.20.

**J2.** The worst band will be **`well-below` or `near-threshold`**, the two
with the highest undetermined share, and **not** `well-above`. The interval is
two bands wide because 76.6% and 75.3% are not meaningfully apart.

**J3.** Its coverage will be **far below** both other scorers — under 60% at
α = 0.20 — because it has almost no ordering to work with.

**J4.** Its AUC will be **below 0.80**, against 0.9489 for the handcrafted
scorer on this benchmark. If it is not, the removed features were carrying
less than claimed and J1 is a weaker test than intended.

## What would falsify the mechanism

**J1 fails.** A scorer with no distance feature does not concentrate, which
would mean the concentration really does come from that feature rather than
from single-threshold calibration. The README's generalisation would come out
and the finding would be restated as being about scorers that encode
distance-from-boundary — still a real result, and a narrower one.

## What would not falsify it

**J2 landing on `above`.** The ordering of middling bands is not the claim.

**J3 or J4 missing.** Both are statements about how weak the crippled scorer
is, not about what one threshold does to it.

## Analysis plan

One run on `fine_dev`, 200 trials, seed 53, appended to
`evidence/fitted_conditional.json` as a third arm. Neither holdout is touched.
