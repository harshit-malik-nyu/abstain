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

---

# Addendum four — does the baseline still fail at scale?

Written before any script runs the plug-in on the fine benchmark.

## The claim being checked

Round two justified the method's extra machinery by beating a plug-in
threshold: accept the smallest τ whose *empirical* calibration rate is within
α, with no finite-sample correction. On 79 cases the plug-in violated in
16.7–20.7% of trials where the conformal rule violated in 0.7–3.3%. That table
is the answer to "why not just pick a threshold?" and it is the reason the
Clopper–Pearson bound is in the method at all.

**It was only ever run on the coarse benchmark**, with 40–50 calibration
cases. The correction it justifies is a *finite-sample* correction: the
empirical rate converges on the truth as n grows, and the gap between a point
estimate and an upper bound shrinks with it. So the comparison may be an
artefact of a small calibration fold, and the honest version of the claim may
be "below some n" rather than "in general".

The fine benchmark gives 202 calibration cases at the 0.30 share — four times
what round two had. If the plug-in holds δ there, the method is
over-engineered at that scale and the README has to say so.

## The design

| | |
|---|---|
| **Set** | `evidence/fine_dev.json`, 672 cases |
| **Arms** | conformal · plug-in, paired per trial |
| **Calibration sizes** | 25, 50, 100, 200, 400 — a sweep, not one point |
| **α** | 0.20, 0.10 |
| **Trials** | 300 |
| **Seed** | 61 |

A sweep rather than a single size, because the interesting output is not a
verdict but **the n at which the correction stops earning its keep**. That is
the number a practitioner needs, and round two could not produce it from two
points on a 79-case pool.

## Predictions

**K1.** The plug-in's violation rate will **fall as calibration grows**, and
be below its round-two figures at every size above 50.

**K2.** At the largest size (400 calibration cases) the plug-in will hold
**δ = 0.05** at α = 0.20. The correction should stop mattering somewhere, and
if it never does I have misunderstood why it works.

**K3.** At the smallest size (25) the plug-in will violate in **more than 15%**
of trials while the conformal rule holds δ. Round two's result should
reproduce on the new benchmark at a comparable calibration size.

**K4.** The conformal rule will hold δ at **every** size, including 25, where
it will instead report infeasible often.

## What this would change

If **K2 holds**, the README's "why not just pick a threshold?" section gains a
qualifier it does not currently have: the plug-in fails at small calibration
folds and is adequate at large ones, and the crossover is reported. That is a
narrower claim than the section currently makes.

If **K2 fails** — the plug-in still violating at 400 calibration cases — the
correction matters at every scale tested and the current claim stands as
written.

**K3 failing** would be the serious one: round two's central comparison not
reproducing on a different benchmark at a comparable size would mean the
justification for the whole method rests on one small pool.

## Analysis plan

One run on `fine_dev`, written to `evidence/plugin_scale.json`. Neither
holdout is touched.

---

# Addendum five — how much rides on a free parameter in the ground truth?

Written before any code re-labels the benchmark. The git history shows it.

## The parameter nobody has questioned

`build_cases.assess` calls a knowledge state **undetermined** when sweeping
the unknown fields either flips the eligibility verdict **or** moves the
benefit amount by more than `material = 50.0` dollars.

That $50 is a choice. It was made once, in the first commit, for a reasonable
reason — an award difference smaller than it is not worth another question —
and it has been the definition of ground truth for every number in this
repository since. **Nothing has ever tested how much the headline depends on
it.**

A reviewer's version of the question: *your ground truth has a free parameter;
is the 49% subgroup failure a property of the world or of the fifty?*

It can be answered with no oracle calls at all. Every state records its
`spread`, and whether the verdict flipped is reconstructible from the complete
enumeration — every household the sweep produces is itself in the benchmark.
So the benchmark can be re-labelled at any materiality and re-run.

## The design

| | |
|---|---|
| **Set** | `evidence/fine_dev.json`, 672 cases, re-labelled per threshold |
| **Materiality** | $0, $25, **$50**, $100, $200, $500, and flip-only (∞) |
| **α** | 0.20 |
| **Trials** | 200 |
| **Seed** | 71 |

`flip-only` is the limit where the amount is ignored entirely and
determinability means the verdict is settled. It is the cleanest test, because
the scorer's diagnosed blindness — far below the income limit, where
eligibility still flips 69% of the time — is about the *flip* criterion, not
the spread one.

## Predictions

**L1.** The concentration on `well-below` will **persist across the whole
non-degenerate range**: above 2× at every materiality from $25 to flip-only.

**L2.** `well-below` will remain the **worst band** at every setting.

**L3.** At **flip-only** the concentration will be **at least as large** as at
$50. The mechanism is about eligibility flipping, so removing the spread
criterion should sharpen it rather than dissolve it.

**L4.** At **$0** the benchmark will degenerate — nearly every state
undetermined, coverage near zero — and that endpoint will be reported as
degenerate rather than as a data point.

## What would falsify the headline

**L1 fails.** If the concentration disappears at some plausible materiality,
then the 49% is a property of the fifty rather than of the problem, and the
README's central result has to be restated as conditional on a parameter
chosen before any of this was known. That would be a serious weakening and it
would go at the top.

## What would not falsify it

**L3 failing** — the concentration shrinking but surviving at flip-only. That
would mean the spread criterion contributes, which is interesting and not
disqualifying.

**L4** in any direction. It is a sanity endpoint.

## Analysis plan

One run on `fine_dev`, written to `evidence/materiality.json`. Neither holdout
is touched. The re-labelling is checked against the committed labels at
$50 — it must reproduce them exactly, or it is re-labelling something else.

---

# Addendum six — the fix the mechanism implies

Written before `award_aware_scorer` exists. The git history shows it.

## Why this round exists

Addendum five established what goes wrong, and it is not a bad feature. The
scorer estimates whether **eligibility** is settled; determinability here
requires the **award** to be settled too. Far below the income limit
eligibility is obvious and the award swings hardest with household size, so
the scorer is confident, right about its own question, and wrong about the one
it is scored on. 72% of its commitments in the failing band are award-only.

Every repair measured so far works *around* that. Group-conditional
calibration gives the failing band its own threshold. Removing the distance
feature blinds the scorer so it stops being confident anywhere. Neither
addresses the actual defect, which is a **missing feature**: nothing in the
score represents how much the award could move.

That is a concrete, agent-computable thing. The award depends strongly on
household size, and the agent knows whether it has been told the household
size. It does not need the oracle to know that an unknown dependent count
makes the award uncertain — only to know that it is unknown.

## What is added

`award_aware_scorer`: the handcrafted scorer plus one term.

The current scorer multiplies by 0.45 when `dependents` is unknown, uniformly.
That is the right *direction* and the wrong *shape*: near the income boundary
the unknown count threatens **eligibility**, which `log_distance` already
handles, while far below it threatens the **award**, which nothing handles.
So the penalty should be **largest where distance is largest** — exactly
inverted from how the current score behaves.

Written out, with `d` the normalised distance from the boundary:

    award_risk = d  if dependents unknown else 0
    score      = handcrafted × (1 − award_risk × k)

with `k = 0.8` fixed here, before any run. No tuning: one value, chosen
because it makes the penalty nearly total at maximal distance, which is where
the measurement says the scorer is most wrong.

## Predictions

**M1.** The concentration on `well-below` will fall **below 2.0**, from 4.13.
This is the mechanism's own prediction and the point of the round.

**M2.** It will do so **without the coverage collapse** that blinding caused.
Coverage will stay **above 70%** — the no-distance scorer reached 1.72 by
giving up the feature entirely, and this keeps it.

**M3.** The pooled unsafe rate will be **at or below** the handcrafted
scorer's 11.1%. Fixing the band that produces most of the failures should
improve the pooled figure, not merely redistribute it.

**M4.** `well-below` will **stop being the worst band**. If the award term
works, the band whose failures were 72% award-only should no longer lead.

**M5.** Group-conditional calibration on top will still help, but by **less**
than it helps the handcrafted scorer — the worst-band improvement should be
smaller than 45.8% → 13.0%, because there is less left to fix.

## What would falsify the mechanism

**M1 fails.** The fix the diagnosis implies does not work, which means the
diagnosis is wrong or incomplete even though two independent measurements
support it. That would go at the top of the README, and the mechanism section
would be rewritten as describing a correlation rather than a cause.

## What would not falsify it

**M3 or M5 missing.** Both are about magnitude rather than direction.

**M4 missing while M1 holds.** A concentration below 2.0 with `well-below`
still nominally worst is the fix working and the band ordering being noisy.

## Analysis plan

One run on `fine_dev`, 200 trials, seed 83, α = 0.20 and 0.15, written to
`evidence/award_aware.json`. Neither holdout is touched. `k = 0.8` is fixed
in this document and is not adjusted afterwards; if the first run disappoints,
that is the result.

---

# Addendum seven — the fix that can actually change anything

Written before `signed_scorer` exists. M1 failed first; this is why, and what
follows from it.

## M1 failed — and the first explanation I published for it was wrong

`award_aware_scorer` multiplied the score down wherever the award was at risk.
It produced results **identical to the handcrafted scorer in every digit** —
pooled 11.5%, coverage 75.8%, concentration 4.07, band by band.

### The wrong explanation, and how it got here

I first wrote that it is a monotone transform, citing **zero order flips in
106,365 state pairs**, and committed that to this document as a measured fact.

**It is false.** The sample was `states_of(cases)[:700]`, which covers only
the first ~44 cases — and `states_of` iterates in case order, so every one of
them fell in the `above` band, where the term does not apply at all. A random
sample of the same size gives **1.41%** flips, and restricted to the states
the rule can actually occupy, **4.65%**.

The claim is retracted. It is left here struck through rather than deleted,
because an unbiased-looking sample that happened to cover one stratum is
exactly the failure mode this repository is about, and I walked into it while
writing about walking into it.

### The real explanation

Both terms apply **only while `dependents` is unknown**, and the greedy
question-selector asks for `dependents` **first, in every case that asks
anything** — 447 of 447.

So the term fires on the opening state and nowhere else. At the opening state
it works, sharply: at τ = 0.3 the handcrafted scorer commits immediately on
225 cases and the award-aware one on **zero**. But an agent that does not
commit immediately simply asks for the household size, the term switches off,
and it commits on the next state — which all three scorers score identically,
because `dependents` is now known.

> **In a sequential rule, a caution term conditioned on an unknown is defeated
> by the agent resolving that unknown.** It bought one extra question and
> changed nothing about what the agent then concluded.

That is a different lesson from the one I first published, and a sharper one.
**M1 is recorded as failed and the scorer is kept**, along with both
explanations, because the retraction is more instructive than the result.

## What the failure points at

The scorer uses **|distance|** from the eligibility boundary. On this
benchmark that makes two very different situations identical:

| | income | log_distance | eligibility | award |
|---|---:|---:|---|---|
| far **below** | $3,000 | 0.861 | settled: eligible | **swings with household size** |
| far **above** | $48,000 | 0.817 | settled: ineligible | zero regardless of size |

Both score ≈ 0.84 and rank together. One is award-undetermined and the other
is fully determined. **The missing feature is the sign**, and unlike a
rescale, adding it changes the order.

It is agent-computable: the agent knows the income it was told and can compare
it to a rough limit, which `features` already does to get the distance.

## What is added

`signed_scorer`: the handcrafted score, with the award penalty applied **only
below** the boundary.

    below      = income < rough limit (or its lower edge when deps unknown)
    award_risk = distance  if below and dependents unknown  else 0
    score      = handcrafted × (1 − award_risk × 0.8)

Same weight, 0.8, carried over unchanged from addendum six. The only
difference is where it applies.

## Predictions

**N1.** The ordering will **genuinely change**: more than 1% of state pairs
will flip relative to the handcrafted scorer.

*Scored after the retraction above: N1 **held** — and it was the wrong guard.
The ordering was never the problem. The problem is that the term switches off
at the agent's first question, which N1 cannot detect.*

*Scored twice, and the two figures differ. The figure first published here was
**2.78%**, measured ad hoc and never written to `evidence/` — which is the
same defect as the retracted claim above in a milder form, since a number no
script computes is a number no test can check. The recorded measurement,
uniform over pairs of reachable states at a fixed seed, is **3.04%**
(`scripts/measure_opening_state.py`, `evidence/opening_state.json`). The
earlier figure is left visible rather than overwritten; it is superseded, not
corrected, because its estimator is no longer recoverable. N1 holds under
both, and the 1% guard is far enough away that the difference changes
nothing — which is luck, not a defence of the practice.*

**N2.** The concentration on `well-below` will fall **below 2.5**, from 4.07.

**N3.** `well-above`'s unsafe rate will **not rise** by more than 3 points.
The penalty is now withheld from that side, and withholding it must not make
it worse.

**N4.** Coverage will stay **above 68%**. Below that the fix is buying safety
by abstaining, which the per-band figures will also show.

## What would falsify the mechanism

**N1 holds and N2 fails.** The order changes, in the direction the diagnosis
says, and the concentration does not move. Then the diagnosis identifies a
real property of the scorer that is not what drives the subgroup failure, and
the README's mechanism section is rewritten as a correlation.

## What would not falsify it

**N3 or N4 missing.** Both are cost predictions.

## Analysis plan

One run on `fine_dev`, 200 trials, seed 89, α = 0.20 and 0.15, written to
`evidence/signed_scorer.json`. Neither holdout is touched. The weight stays at
0.8; if the sign is not the missing piece, that is the result.

---

# Addendum eight — attacking the result that refuted the central claim

Written before `scripts/run_no_distance_groups.py` exists. The git history
shows it.

## Why this round exists

J1 refuted the strongest form of this repository's central claim. I had
predicted that removing the distance feature would *not* fix the subgroup
concentration, because the concentration was a property of using one threshold
rather than a property of the scorer. It did fix it: 4.13 → **1.72**, and
`hides_a_subgroup` went False — every band inside the budget.

That refutation has been reported prominently for two rounds and has never
been attacked the way the claim it refuted was. It should be, because it has
a visible weakness:

| α | no-distance worst band | budget | inside? |
|---:|---:|---:|:--:|
| 0.20 | 12.48% | 20% | yes |
| 0.15 | 11.65% | 15% | yes |
| 0.10 | — | 10% | **not measured** |

**The worst band barely moves with the tolerance** — 12.48% to 11.65% while
the budget falls by a quarter. That is not a rule tracking its budget; that is
a roughly fixed failure rate with the budget sliding past it. If the pattern
continues, the band sits above 10% at α = 0.10 and the "every band inside the
budget" result is a property of the two tolerances that happened to be
measured.

Group conditioning was never run on this scorer either — `schemes` in
`evidence/fitted_conditional.json` carries `handcrafted` and `fitted` only. So
the question "does conditioning still add anything once the feature is gone?"
has been open since the round that made it interesting, and the README has
been comparing a *pooled* no-distance rule against a *group-conditioned*
handcrafted one without saying so.

## What is added

No new method. `run_no_distance_groups.py` runs the arm that was skipped:
`fitted_no_distance_scorer` at α = 0.20, 0.15 **and 0.10**, pooled and
by-band, 200 trials, `fine_dev`, refit every trial on a fold disjoint from
calibration and deployment — the same protocol as round J.

## Predictions

**O1.** At α = 0.10 the no-distance scorer's worst band will be **above 10%**
and `hides_a_subgroup` will be **True**. The apparent conditional validity at
0.20 and 0.15 is the budget moving past a near-constant failure rate.

**O2.** Its worst-band rate at α = 0.10 will be **within 2 points of its rate
at α = 0.20** (12.48%), on the same reasoning — the rate is close to
insensitive to the tolerance.

**O3.** Group conditioning on this scorer will bring the worst band **under
the tolerance** at α = 0.10 in the feasible trials. Conditioning still adds
something after the feature is removed.

**O4.** It will cost feasibility, and more at α = 0.10 than at α = 0.20:
fewer than 190 feasible trials out of 200 at α = 0.10.

**O5.** `well-below` will remain the worst band at every tolerance under the
pooled rule. Removing the feature shrinks the disparity without changing which
group bears it — this is J2 continuing to hold.

## What would falsify what

**O1 fails** — the no-distance scorer holds every band inside a 10% budget.
Then removing the feature delivers *conditional* validity on this benchmark
without any conditioning, which is a stronger result than anything currently
in the README, and the recommendation should lead with the feature audit
rather than with conditioning. This would be good news reported as good news.

**O3 fails while O1 holds** — the feature is gone, the subgroup failure is
back at a tighter tolerance, and conditioning cannot fix it either. Then the
remedy section is wrong about what conditioning is for, and the honest
conclusion is that at α = 0.10 on 672 cases there is no remedy, only a
sample-size requirement.

**O2 or O4 missing** is uninformative. Both are shape predictions.

## What this cannot show

α = 0.10 is close to the arithmetic floor for group conditioning on this
benchmark — [`power.py`](../src/abstain/power.py) puts the by-band arm at
roughly 50 cases per group and `fine_dev`'s 30% fold gives about 50 total per
band. So a low feasible count at α = 0.10 is **expected** and is not evidence
against conditioning; it is the cost the method already reports. O4 exists to
record the size of that cost, not to argue from it.

## Analysis plan

One run on `fine_dev`, 200 trials, seed 53 — the seed round J used, so the
arms are paired against the figures already published — α = 0.20, 0.15, 0.10,
written to `evidence/no_distance_groups.json`. Neither holdout is touched.
Nothing below α = 0.10 is attempted and no prediction is adjusted after a
result.
