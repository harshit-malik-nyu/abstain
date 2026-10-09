# A selection rule that bounds how often an agent answers blind

An agent conducting a benefits intake can ask for a field or commit to a
verdict. Committing while the case is still undecidable is the failure that
matters, because downstream it becomes a filed claim built on a guess. A
companion benchmark measured a frontier model doing exactly that on **62.5%**
of undecidable cases.

This is a rule where the operator names a tolerance and gets it:

> give me an unsafe rate at or below α, and resolve as much as possible
> subject to that

**It holds**, on a pre-registered holdout and again on an independent
benchmark eight times larger.

The useful part of this repository is what came out of attacking it
afterwards: **four bugs, every one of which made the method look better than
it was; twenty-six pre-registered predictions that missed; and one result that
changes what the method is for.** The guarantee it delivers is not the
guarantee its own README advertised for four rounds, and the gap is not small
— and the strongest form of the claim that replaced it was refuted by its own
pre-registered test, two rounds later.

Everything below is measured. Every figure is checked against the file that
produced it by a test, every pre-fix run is kept in `evidence/` beside the
fix, and **[all seventy-three predictions are listed with their
outcomes](docs/predictions.md)** — a test parses that table and requires the
count above to match it, because the opening said "five" for a while and was
wrong.

---

## The finding that matters most

The guarantee is **marginal**. It bounds the error rate over the population and
says nothing about any subgroup of it. That is the standard caveat on split
conformal methods, usually written in a limitations section and left there.

Measured on **held-out data** — 672 cases, 400 trials, α = 0.20:

| | |
|---|---:|
| Trials where the rule honoured its budget **overall** | **100%** |
| Trials where it broke that budget **for some income band** | **99.8%** |

The band is always the same one. `well-below` — households under $6,000 of
employment income — runs at **49.0% unsafe** against a 20% budget, absorbing
**4.2×** its proportional share, while the headline number reads 11.5%.

Development data said the same thing slightly less starkly: 98.5% against
98.2%, with that band at 45.7%. **The holdout is worse**, which is the
direction that cannot be explained by having tuned anything.

Those are the applicants most likely to be eligible and least able to absorb a
wrong decision. **At a stated 20% tolerance they receive a decision built on a
guess nearly half the time, and the pooled certificate says the rule is
working.**

### With honest error bars

That 49.0% pools 26,752 deployed cases — but they are **96 distinct
households** appearing about 279 times each, once per trial. A standard error
computed from 26,752 would claim ±0.6 points, which is not optimistic so much
as answering a different question: how precisely the rate is known *for these
96 households*, when the claim is about households like them.

Resampling **cases** rather than observations, 5,000 draws:

| band | cases | rate | 95% CI (cluster) | naive ± | cluster ± |
|---|---:|---:|---:|---:|---:|
| **well-below** | 96 | **49.0%** | **[39.9%, 58.4%]** | 0.6% | **9.5%** |
| near-threshold | 192 | 6.3% | [3.7%, 9.2%] | 0.2% | 2.9% |
| above | 128 | 7.1% | [3.1%, 11.9%] | 0.3% | 4.8% |
| well-above | 256 | 3.7% | [1.5%, 6.1%] | 0.1% | 2.4% |

**The correct interval is sixteen times wider than the naive one** — and the
conclusion is unchanged. The lower bound is 39.9% against a 20% budget, and
the finding clears its tolerance at both α on both halves:

| | α = 0.20 | α = 0.15 |
|---|---|---|
| dev | 45.7%, lower bound **36.4%** | 29.0%, lower bound **21.0%** |
| holdout | 49.0%, lower bound **39.9%** | 31.9%, lower bound **24.0%** |

Nothing in that bootstrap is novel. What would have been novel is reporting
the naive interval.

### And it is not an artefact of where the lines were drawn

The finding above is stated **per band**, and `well-below` is `income ≤
6,000` — three values out of twenty-one on this benchmark's income grid, 96 of
672 cases, under three cutoffs written by hand in
[`scripts/split.py`](scripts/split.py). Round five swept the *other*
hand-chosen constant, materiality, across two orders of magnitude and found
the concentration unmoved. The partition had never been swept, and it is the
more dangerous of the two because the finding is phrased in its terms.

`split.py` is the first commit in this repository, so the cutoffs cannot have
been tuned to the result. That rules out tuning. It does not rule out luck.

Nine partitions, tallied from the **same trajectories** — one deployment pass
per tolerance with the collectors fanned out, so the only thing varying is the
grouping — at α = 0.20:

| partition | poorest band | its rate | concentration | subgroup hidden? |
|---|---|---:|---:|:--:|
| **equal-count quartiles** *(neutral)* | ≤ 15,000 | **27.3%** | **2.46** | **yes** |
| published | ≤ 6,000 | 45.9% | 4.13 | yes |
| bottom cutoff at 3,000 | ≤ 3,000 | **53.7%** | **4.83** | yes |
| bottom cutoff at 9,000 | ≤ 9,000 | 41.8% | 3.76 | yes |
| bottom cutoff at 12,000 | ≤ 12,000 | 33.9% | 3.05 | yes |
| **two bands at the median** | ≤ 30,000 | 15.8% | 1.42 | **no** |

**The neutral partition is the one that matters.** Equal-count quartiles are
chosen by the income distribution with no reference to any result, and they
split 191/162/155/164 against the hand-drawn 96/192/128/256. The poorest
quartile still runs at 27.3% against a 20% budget while the pooled rate is
inside it. **The subgroup result is not an artefact of three constants.**

Two things the sweep found that were not predicted:

**A coarse partition hides it completely.** Two bands at the median report a
worst group of 15.8% and no hidden subgroup, at *both* tolerances. An operator
who checks for subgroup failure with two groups concludes there is none. If you
take one practical thing from this section, take that: **the check is only as
good as the partition, and "we looked at subgroups" is not a finding without
saying which.**

**Under the neutral partition the detection is tolerance-sensitive.** At
α = 0.15 the poorest quartile comes in at **14.54% against 15%** — inside the
budget by 0.46 points, so nothing is flagged, while the published partition
flags it at both tolerances. The quartile is twice as wide as `well-below` and
dilutes accordingly. That is a real limit on the claim and 0.46 points is not
a margin to rely on in either direction.

The monotone fall from 4.83 to 2.46 as the bottom cutoff widens is dilution,
and the direction is the point: **the effect lives at the bottom of the income
range**, not spread evenly through `well-below`. Six of seven predictions held;
the one that missed is in [the ledger](docs/predictions.md) with why it could
not have passed.

### The mechanism is not what it looks like

Not bad ranking. The scorer orders states *almost perfectly* inside the band it
fails on:

| band | AUC | mean score, undetermined states |
|---|---:|---:|
| **well-below** | **0.9976** | **0.2106** |
| near-threshold | 0.9345 | 0.1131 |
| above | 0.9822 | 0.0499 |
| well-above | 0.9833 | 0.0593 |

What differs is where the score **levels** sit. Undetermined states score about
twice as high in `well-below` as in `near-threshold`. One global threshold is a
single horizontal line drawn across four vertically shifted distributions, so
it cuts each band at a different quantile.

> **Good ranking within every subgroup does not give a threshold that is safe
> within every subgroup. Conditional validity needs conditional
> *calibration*, not conditional ranking.**

### Why those levels are shifted

"Shifted levels" is a description, not a cause. The cause is specific, and the
explanation I expected was wrong.

Determinability here fires on two conditions: the eligibility verdict flips
across the unknown fields, **or** the benefit amount moves materially while
the verdict is stable. The natural story was that `well-below` is dominated by
the second — households obviously eligible on income whose *award* still
swings with household size — and that a scorer measuring distance from the
*eligibility* boundary is blind to that by construction.

I rejected that, then over-corrected, and the full account took three passes.
All three are kept, because the sequence is the honest record — and the middle
one is where I was most confident and least right.

**Pass one — rejected.** Across *all* undetermined states the award-only share
is `well-below` 31%, `near-threshold` 42%, `above` 15%, `well-above` 14%. Not
a majority for the failing band, so the hypothesis looked dead.

**Pass two — over-corrected.** The rule does not meet undetermined states
uniformly; it commits on the **high-scoring** ones. Measured there:

| band | unsafe commitments | **award-only** | share |
|---|---:|---:|---:|
| **well-below** | 1,165 | **834** | **72%** |
| near-threshold | 232 | 89 | 38% |
| above | 208 | 0 | 0% |
| well-above | 385 | 77 | 20% |

**72%, not 31%** — a real measurement, and the selection effect behind it is
the one [`calibrate_on_trajectories`](src/abstain/rule.py) exists to handle.
I then promoted it to *the cause*, which it is not. It answers **why those
states are undetermined**. It does not answer **why the scorer is confident
about them** — a different question I had merged into it.

**Pass three — the two questions, kept apart.** Take the two bands with
near-identical base rates of safe states whose concentrations differ eightfold:

| band | safe partial states | open states | median score | **share above 0.3** | concentration |
|---|---:|---:|---:|---:|---:|
| **well-below** | 12.5% | 588 | 0.3767 | **100%** | **4.07** |
| near-threshold | 13.8% | 1,159 | 0.2884 | **45%** | 0.50 |

Same base rate. **Every one of `well-below`'s unsafe states sits above 0.3;
fewer than half of `near-threshold`'s do.** What differs is not how many states
are unsafe — it is *where the unsafe ones sit on the scale*.

So the account has three parts and only the third is the mechanism:

1. **Why are those states undetermined?** The award moves — 72% of the rule's
   failures there are award-only.
2. **Why is the scorer confident about them?** Its one real feature is distance
   from the eligibility boundary, maximal far *below* the limit, where
   eligibility is settled and the award is not.
3. **Why does that concentrate harm?** One threshold cuts a band whose unsafe
   states are 100% above it at a completely different effective quantile than
   one where 45% are.

**A base-rate explanation was tested and rejected too**: bands at 12.5% and
13.8% safe produce concentrations of 4.07 and 0.50, so base rate does not
predict harm here.

Part 2, measured over undetermined states where income is known:

| band | undetermined states | share scoring **0** | median score | mean distance-from-boundary |
|---|---:|---:|---:|---:|
| **well-below** | 588 | **0%** | **0.3767** | **0.8759** |
| near-threshold | 1,159 | 34% | 0.2884 | 0.5115 |
| above | 663 | 77% | 0.0000 | 0.1849 |
| well-above | 667 | 19% | 0.3073 | 0.6382 |

**Not one undetermined `well-below` state scores zero** — every other band has
undetermined states the scorer rates at exactly zero, which is the scorer
saying *it cannot tell* — and `well-below`'s median is the highest of any band.
The last column is why: the score tracks distance from the income limit, and
that distance is largest precisely where the limit is furthest away.

Parts 1 and 2 together make the mechanism sharper than "a feature that is
wrong":

> **The scorer answers a different question than the one it is scored on.** It
> estimates whether *eligibility* is settled, and for households far below the
> limit it is right — they are eligible. But determinability here requires the
> *award* to be settled too, and far below the limit the award swings hardest
> with household size. The scorer is confident, correct about its own
> question, and wrong about the one that counts.

That is why the failure is systematic rather than noisy, and why it is
group-correlated: the two questions diverge most exactly where income is
lowest. A single global threshold cannot correct a bias that is consistent
within a group and different between groups. A per-group threshold can,
because inside a band the gap between the two questions is at least stable.

**Independently confirmed by removing the second question.** Re-label the
benchmark so determinability means *eligibility settled* and nothing else, and
the concentration falls from **4.07 to 1.55** with a different worst band. If
`well-below`'s failures were mostly eligibility flips, that could not happen.

> Which generalises past this benchmark: **a confidence feature encoding
> "far from the decision boundary along dimension X" is systematically
> overconfident on exactly the cases where a different dimension decides** —
> and systematic, group-correlated overconfidence is the kind a single
> threshold cannot absorb.

How much of the concentration is *this feature* rather than *any* single
threshold is measured two sections below, and the answer is "most of it".
Removing the feature cuts the disparity from 4.13× to 1.72×. I predicted it
would not, and wrote that prediction down first.

### How much of this is the scorer? I predicted "none of it" and was wrong

Everything above rests on one hand-built scorer, and the mechanism blames one
hand-written feature. I claimed the concentration was a property of **using one
threshold**, not of that feature, and pre-registered two tests of it: a scorer
that *learns* its weights over the same features, and a scorer that **cannot
see distance from the boundary at all**. Both refit every trial on a fold
disjoint from calibration and deployment.

α = 0.20, 200 trials, `fine_dev`:

| scorer | AUC | pooled unsafe | coverage | worst band | its rate | concentration | hides a subgroup |
|---|---:|---:|---:|---|---:|---:|:--:|
| handcrafted | **0.9555** | 11.1% | 76.0% | `well-below` | **45.9%** | **4.13** | **yes** |
| fitted | 0.9252 | 11.8% | 88.1% | `well-below` | 39.2% | **3.31** | **yes** |
| **fitted, no distance feature** | **0.8888** | **7.3%** | **92.7%** | `well-below` | **12.5%** | **1.72** | **no** |

**The strong claim is refuted.** Dropping the one feature the mechanism blames
cuts the concentration from 4.13 to **1.72** and puts every band inside the
budget *on this estimator* — a qualification added two rounds later, after
[round O](#i-attacked-that-result-too-and-it-corrected-a-claim-of-mine) found
that the sentence was false of one deployment in four. Had I not written the
prediction down, "a single threshold concentrates harm" is exactly the kind of
claim that survives on two confirming arms.

What survives is narrower and still worth having:

> The concentration is driven **primarily by a score feature that is
> systematically wrong for one group**, and a single threshold cannot absorb
> that. It is not an artifact of the hand-built functional form — learning the
> weights over the same features leaves 3.31. Remove the feature and the
> disparity shrinks 2.4×; it does **not** vanish. The same band is still worst
> at 1.72× its share.

So a single threshold contributes, and here it is not the dominant term. The
practical reading is more useful than the claim it replaces: **a feature that
is directionally wrong for a group is the thing to look for first.** What it
does *not* support — and I wrote that it did — is that removing the feature
beat every alternative. On the per-trial measure it matches conditioning at
α = 0.20 and is far worse at α = 0.15, which is the next section.

**J1, J3 and J4 all missed, in the same direction: I badly underestimated the
crippled scorer.** J3 predicted its coverage would fall below 60% — it is
**92.7%**, the highest of the three. J4 predicted AUC below 0.80 — it is
0.8888. **J2 held**: the same band is still worst. **H3 missed** too, in the
other direction: I predicted the fitted scorer's pooled rate would be at or
below the handcrafted one's, and it is higher at both tolerances, because it
commits far more often while resolving twelve points more.

### I attacked that result too, and it corrected a claim of mine

The refutation above had been the most prominent thing in this section for two
rounds and had never been attacked the way the claim it refuted was. It has a
visible weakness: the no-distance scorer's worst band moves only 12.48% →
11.65% as the budget falls from 20% to 15%, which is what a fixed failure rate
with a sliding budget looks like rather than a rule tracking its budget. So
[addendum eight](docs/preregistration-5.md) predicted it would break at
α = 0.10.

**It does not.** At α = 0.10 the worst band falls to **3.79%** and coverage
rises to **97.79%**. The two-point extrapolation was the error, not the
hypothesis: at that threshold the rule asks nearly everything, full
information always resolves, and the rate collapses. Three of five predictions
missed.

**And the concern behind them was right, on an estimator I had not thought to
name.** Same arm, same tolerances, two ways of counting:

| | α = 0.20 | α = 0.15 | α = 0.10 |
|---|---:|---:|---:|
| worst band, pooled across 200 trials | 12.48% | 11.65% | **3.79%** |
| trials where **some** band exceeded α | 2.5% | **24.5%** | **26.0%** |
| questions per case | 2.00 | 2.08 | **2.72** |
| coverage | 92.75% | 93.24% | **97.79%** |

Both rows are honest and they say different things, because one averages over
trials and the other counts failures. **A quarter of deployments put a band
over budget while the across-trial rate sits comfortably inside it**, so
"removing the feature brings every band inside the budget" is true of the first
row and false of the second. That is the same unit-of-aggregation error as
[the third bug](#the-guarantee-was-conditional-on-feasibility-and-the-metric-was-not)
and as the naive-versus-cluster interval — the third time in this repository,
and the first time in a claim of mine rather than in a metric's behaviour.

Against conditioning on the per-trial measure, which is the comparison the
earlier section should have made:

| α | handcrafted + conditioning | no-distance, one threshold | no-distance + conditioning |
|---:|---|---|---|
| 0.20 | 2.6%, 196/200 feasible | **2.5%, 200/200** | **1.1%, 187/200** |
| 0.15 | **8.3%, 120/200** | 24.5%, 200/200 | **4.0%, 99/200** |
| 0.10 | 0.0%, **3/200** | 26.0%, 200/200 | — **0/200** |

**Removing the feature matches conditioning at α = 0.20 and is three times
worse at α = 0.15.** The two together beat either alone wherever both are
feasible. And at α = 0.10 on 672 cases there is **no remedy to buy**:
conditioning is infeasible in every trial for both scorers, so the per-group
certificate is not available at any price and all that is left is a
better-behaved score whose per-group behaviour is measured rather than
guaranteed.

One more thing that table changes. The cost of tightening here is **questions,
not coverage** — 2.00 to 2.72 per case while coverage *rises* five points.
This README frames the trade as safety against coverage throughout, and for a
scorer that is right about its own question the trade is safety against
interrogation, which is the more useful framing whenever the question budget
is not the binding constraint.

### The fix works on the learned scorer too

**H4 held.** Group-conditional calibration, measured on the same bands, with
the fitted scorer refit per trial:

| scorer, α = 0.20 | violations per band | worst band | coverage |
|---|---:|---:|---:|
| handcrafted, one threshold | 99.0% | 45.8% | 76.0% |
| handcrafted, **per band** | **2.6%** | **13.0%** | **80.3%** |
| fitted, one threshold | 86.5% | 38.9% | 88.1% |
| fitted, **per band** | **7.0%** | **12.1%** | **92.0%** |

Pareto again, on a scorer the fix was never designed around: safer in every
band and four points more coverage. The feasibility cost is the same one —
186 of 200 trials at α = 0.20, 93 of 200 at α = 0.15.

### A fourth result about AUC, and this one points backwards

Look at the first two columns of that table together. **The scorer with the
worst AUC has the lowest pooled unsafe rate and the highest coverage.** 0.8888
against 0.9555, and it is better on both axes the method actually optimises.

That is the fourth of five independent results here that AUC cannot see what
this method does, and the first where it points in the wrong direction rather
than merely failing to discriminate. A ranking metric scores a scorer on pairs it will
never be asked about; a threshold-local rule is judged on one cut.

### A fifth, and the one that should change how these things are measured

Two further rounds tried to repair the scorer at the feature level rather than
work around it. Both failed, and failing produced the sharpest result in this
repository.

The diagnosis says the score is missing a term for how much the **award** could
move. So: add one. `award_aware_scorer` penalises the score wherever the award
is at risk; `signed_scorer` does it only *below* the boundary, so it reorders
states instead of merely rescaling them. Weight 0.8, fixed in
[addendum six](docs/preregistration-5.md) before either existed.

These are three different functions by every measure taken of the functions
themselves:

| scorer | AUC | reachable state pairs reordered vs handcrafted | cases answered with no question asked, τ = 0.3 |
|---|---:|---:|---:|
| handcrafted | 0.9555 | — | 225 of 672 |
| award-aware | **0.9425** | **4.77%** | **0** |
| **signed** | **0.9604** | **3.04%** | 129 |

And they are **one policy**:

| | pooled | `well-below` | near-thr. | above | well-above | coverage | q/case | concentration |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| handcrafted | 11.29% | 45.93% | 5.69% | 5.53% | 5.39% | 76.04% | 2.0525 | 4.0691 |
| award-aware | 11.29% | 45.93% | 5.69% | 5.53% | 5.39% | 76.04% | 2.0525 | 4.0691 |
| signed | 11.29% | 45.93% | 5.69% | 5.53% | 5.39% | 76.04% | 2.0525 | 4.0691 |

Not identical to the precision shown — **identical under `==`**, across both
tolerances, every band rate, every band's coverage, every concentration, and
the group-conditional arms too (pooled 98.5% / 45.67%, by-band 5.26% / 12.94%,
190 feasible trials, all three). A test asserts the equality rather than a
table asserting it, because a printed figure at one decimal cannot support a
claim this strong.

**Why.** Both terms are gated on `dependents` being unknown, and the greedy
selector asks for `dependents` **first in all 447 cases that ask anything**. So
the terms act on the opening state and nowhere else. They work there — sharply,
the award-aware scorer commits immediately on *zero* cases against 225 — and an
agent that does not commit immediately asks the one question that switches the
term off. It then commits on the next state, which all three score identically
because `dependents` is now known.

> **In a sequential rule, a caution term conditioned on an unknown is defeated
> by the agent resolving that unknown.** It buys one question and changes
> nothing about what the agent concludes.

Which makes AUC's failure here qualitatively worse than the fourth result.
There it ranked a better policy lower. Here it moved **in both directions**,
by 0.0179 — more than the gap between arms elsewhere in this README that *did*
change behaviour — while the deployed rule did not move in any digit.

> **A confidence function for a sequential agent cannot be evaluated on the
> state space. It has to be evaluated on the states the agent reaches under the
> rule.** The state space contains the pairs the added terms reorder. The rule
> never visits them.

Nine predictions across the two rounds, **five missed, and the four that held
did so vacuously** — every one was a cost prediction, and a no-op has no cost.
`docs/predictions.md` labels them that way and a test requires the label,
because four of nine holding is otherwise a round that reads like a partial
success and was not one.

### It is the stopping rule, not the asking rule

The rule does two things — decides **when** to stop asking, and **what** to
ask next — and the finding is attributed entirely to the first. A question
policy that happened to serve one band badly would look identical, so that is
ruled out rather than assumed. 200 trials, α = 0.20, everything else fixed:

| question policy | pooled | `well-below` | concentration | worst band | questions |
|---|---:|---:|---:|---|---:|
| greedy one-step lookahead *(default)* | 11.1% | 45.8% | 4.13 | `well-below` | 2.05 |
| fixed order, blind to the case | 11.1% | 45.8% | 4.13 | `well-below` | 2.05 |
| random order, seeded per state | 12.5% | 42.9% | 3.43 | `well-below` | **2.42** |

**The same band fails under every policy**, and randomising the question order
buys 2.9 points off it while costing 0.37 more questions per case. At α = 0.15
it is *worse* — 32.6% against 29.5%. **You cannot fix this by changing what
you ask, only by changing when you stop**, which is exactly where
group-conditional calibration intervenes.

One thing fell out of that table. The greedy policy and the blind fixed order
are **bit-identical**, because the scorer's penalties for unknown fields are
case-independent constants — so the expected one-step gain ranks the same way
for every case, and the "adaptive" lookahead is a constant order wearing a
costume. Worth knowing before attributing anything to it.

### The rule never abstains on the band it fails

Under one global threshold, `well-below`'s abstention rate is **0.0%**.
Coverage 54.3% plus unsafe 45.7% is 100%: it commits on every single case.

That band's undecidable states carry the highest score levels of any band, so
they clear a globally-set threshold immediately — and the abstention mechanism,
which is the entire point of the method, is **inactive exactly where it is
most needed**.

### A global threshold mis-allocates questions, not just risk

This is the mechanism, and it is measured rather than inferred. Questions per
case, per band, α = 0.20:

| band | one global threshold | one per band | Δ |
|---|---:|---:|---:|
| **well-below** *(45.7% unsafe)* | **1.67** | **2.15** | **+0.48** |
| near-threshold | 2.28 | 2.29 | +0.01 |
| above | 2.41 | 2.26 | −0.15 |
| well-above | 1.85 | 1.31 | **−0.54** |

**The global threshold asks the fewest questions of the applicants whose
answers are least determined**, and the most of a band that barely needs them.
Per-band calibration moves half a question from `well-above` to `well-below`
and the total *falls* — 1.89 against 2.06.

So this is not a safety–coverage trade. Raising `well-below`'s threshold
raises its abstention only from 0.0% to 2.0%; what it mostly buys is **one
more question**, after which the case is decidable and a blind commitment
becomes an informed resolution:

| `well-below`, α = 0.20 | unsafe | coverage | abstains | questions |
|---|---:|---:|---:|---:|
| one global threshold | **45.7%** | 54.3% | 0.0% | 1.67 |
| one per band | **5.6%** | **92.4%** | 2.0% | 2.15 |

An **8× reduction in unsafe commitments and 38 points more coverage**, for
half a question. The least-served band across the whole benchmark rises from
54.3% to 70.8%.

The cost lands on `well-above`: 5.4% → 10.8% unsafe, still well inside a 20%
budget, coverage 88.4% → 85.8%. It was being over-protected by a threshold set
for someone else and now spends its own budget. At α = 0.15 the least-served
band is marginally worse for the same reason (65.4% → 63.2%).

### The fix is not a trade-off

Group-conditional calibration — one threshold per band, which is Mondrian
conformal prediction and not new — on the same cases, paired per trial:

| α = 0.20 | violations (pooled) | **violations (per band)** | **worst band** | coverage | questions/case | infeasible |
|---|---:|---:|---:|---:|---:|---:|
| One global threshold | 1.5% | **98.2%** | **45.6%** | 76.0% | 2.06 | 0% |
| **One per band** | 0.0% | **3.3%** | **12.9%** | **81.0%** | **1.89** | 2.8% |
| Two groups *(post-hoc)* | 0.2% | 62.3% | 24.1% | 79.0% | 1.92 | 0% |

I pre-registered that group conditioning would **cost** coverage — four
conservative thresholds abstain more than one. **That prediction was wrong.**
It is safer per band, resolves *more*, and asks *fewer* questions.

The reason is the mechanism above. A single threshold has to be high enough to
control the pooled rate, which is dominated by one band's high-scoring
undecidable states — and that threshold then over-abstains in the three bands
that never needed it. **The global threshold was simultaneously too low for one
band and too high for three.** The pooled rule was not on the safety–coverage
frontier at all; conditioning does not trade along the frontier, it moves onto
it.

The only real cost is feasibility, and it is a sample-size cost: 2.8%
infeasible at α = 0.20, 34% at α = 0.15. [`src/abstain/power.py`](src/abstain/power.py)
gives the closed form for how much calibration data buys which tolerance.

The two-group scheme is instructive and is why the full version is the one to
use: separating the band you *know* fails leaves the bands you did not check
sharing a threshold, and one of them then exceeds the budget.

[Full results for rounds two to four →](docs/results-secondary.md)

---

## Why not just pick a threshold?

The method's extra machinery is one line: a Clopper–Pearson upper bound at δ
in place of the empirical rate. The baseline — accept the smallest threshold
whose *observed* calibration rate is within α — is what a competent engineer
writes, and it is correct **in expectation**, which is exactly why it fails. An
operator who asks for 5% and gets 5% on average is over budget half the time.

Same pipeline, same grid, 300 trials on the 672-case benchmark, swept across
calibration size — because the correction it justifies is a *finite-sample*
correction, and the obvious objection is that it stops mattering once you have
data:

| Calibration cases | α = 0.20 conformal | α = 0.20 plug-in | α = 0.10 conformal | α = 0.10 plug-in |
|---:|---:|---:|---:|---:|
| 25 | **2.1%** | **36.3%** | *declines* | **46.7%** |
| 50 | **1.3%** | **35.0%** | **0.3%** | **39.0%** |
| 100 | **0.3%** | 19.7% | **0.7%** | 29.7% |
| 200 | **2.3%** | 8.7% | **0.3%** | 17.3% |
| 400 | **1.0%** | **16.0%** | **1.0%** | 6.3% |

**It does not stop mattering.** The plug-in never holds δ = 0.05 at any
calibration size tested — up to 400 cases, five times what the original
comparison had and most of the available pool — and at α = 0.20 its violation
rate is not even monotone, rising again from 8.7% to 16.0%.

**K1 and K2 both missed, and being wrong improved the explanation.** I had
described this as a finite-sample correction that should dissolve with data,
and pre-registered that the plug-in would hold δ at 400 cases. It does not,
because the failure was never about sample size:

> The plug-in chooses the smallest threshold whose **point estimate** sits at
> α. A point estimate at α is above α about half the time, so the deployed
> rate crosses the budget by construction. More calibration data makes that
> targeting *more precise* — it lands *closer* to α — which does not reduce
> the crossings. The 46.7% at the smallest fold is that mechanism with the
> noise stripped away.

The conformal rule holds δ at every size, and where it cannot it **declines**:
at 25 cases and a 10% tolerance it reports infeasible in 100% of trials rather
than offering a threshold. The plug-in never reports infeasible. It always has
a threshold to offer, and the threshold is not safe.

---

## Does the bound survive a bad score?

`rule.py` claims the guarantee holds for *any* fixed score — which makes score
quality a coverage question, not a safety question. That is a strong claim and
it had never been tested, because the repository had exactly one scorer and it
worked.

Eight corruptions, each applied identically in calibration and deployment so
exchangeability is held fixed while quality varies. Dev, 150 trials,
violations over feasible trials:

| corruption | Kendall τ | violations | coverage |
|---|---:|---:|---:|
| identity | 1.000 | 2.0% / 0.7% / 0.7% | 72.9% |
| coarse — round to tenths | 0.981 | 0% | **65.2%** |
| sharpen — monotone | **1.000** | 0% | 75.2% |
| noisy(0.10) | 0.755 | 3.9% | **40.4%** |
| noisy(0.25) · noisy(0.50) · constant · **inverted** | 0.63 → **−1.00** | **no feasible trial** | — |

**Nothing violates.** Everything degrades through coverage and then through
infeasibility — the rule stops certifying itself rather than certifying
something false. The worst case tested is the exact negation of a good score.

> The guarantee is a **safety** guarantee, not a **usefulness** guarantee, and
> on this benchmark the difference is 73% coverage against 0%.

**This is also the quantitative answer to the objection that no language model
was run.** Model confidence clumps on round values and is imperfectly ordered,
and both are in the table: rounding alone costs 8 points of coverage and makes
a 10% tolerance infeasible 23% of the time. Mild rank noise — τ = 0.755, a
plausible description of self-reported confidence — collapses coverage from
72.9% to 40.4%. **A conformal abstention wrapper on a badly-ordered confidence
signal is safe and nearly useless**, which is worth knowing before building
one and is not what "any fixed score" suggests at first reading.

---

## What breaking the assumption costs, and the certificate that never notices

Every guarantee here rests on exchangeability, and until round five the
repository asserted that and never priced it. The bands make it measurable:
calibrate on the natural mix, deploy on a mix where `well-below`'s share is
forced upward. 300 trials per point, α = 0.20.

![Violation rate against a 20% tolerance as the deployed applicant mix shifts
toward the lowest-income band. A single global threshold climbs from 0.7% to
98% of trials violating; one threshold per band never leaves 0.7%; and the
bound the method reports stays at 0.175
throughout.](docs/shift.svg)

| `well-below` share of deployment | one global threshold | **one per band** | the bound the rule reported |
|---:|---:|---:|---:|
| 14.3% *(natural)* | 0.7% | 0.0% | 0.175 |
| 25% | 17.0% | 0.0% | 0.175 |
| 40% | **65.3%** | 0.0% | 0.175 |
| 60% | **92.3%** | 0.0% | 0.175 |
| 80% | **95.3%** | 0.0% | 0.175 |
| **100%** | **98.0%** | **0.7%** | **0.175** |

**All five pre-registered predictions held.** Three things in that table.

**The pooled rule collapses.** 0.7% → 98.0% violations as the applicant mix
moves toward one band. Monotone throughout. Nothing about the rule changed;
only who showed up.

**Group conditioning is essentially immune — 140× better at full shift.** This
is not a lucky robustness property, it is the construction: re-weighting groups
that were calibrated separately changes *which* thresholds get used, not *what
any threshold is.* The guarantee was never a statement about the mixture.

> So the fairness finding and the robustness finding are the same finding. The
> subgroup that absorbs the error budget is exactly the subgroup whose
> over-representation breaks the pooled rule, and one threshold per group fixes
> both at once.

**And the failure is perfectly silent.** The last column is the method's own
confidence statement. It reads **0.175 at every shift level** — flat, while the
deployed violation rate goes from 0.7% to 98.0%. The bound is computed on
calibration data, calibration data is unshifted, so the certificate is
identical whether the rule is honouring its budget or breaking it 98% of the
time. **An operator watching the reported bound would see nothing wrong.**

[Round five →](docs/preregistration-5.md) · run in
[`evidence/round5-run.txt`](evidence/round5-run.txt)

### "Just recalibrate" — the obvious rebuttal, tested

Calibration is held at the natural mix in that table, which models the *onset*
of a shift and invites a one-line reply: of course it fails, you never let it
recalibrate. If that reply were right, the advice from this project would
collapse to *recalibrate when your population moves* — easier, and already
standard practice.

So the same sweep was run with the calibration fold reweighted to match the
deployment fold. The operator knows the mix and has recalibrated on it.

| `well-below` share | pooled violations, **stale** | pooled violations, **recalibrated** | recalibrated **worst band** | concentration | hides a subgroup |
|---:|---:|---:|---:|---:|:--:|
| 14.3% *(natural)* | 0.7% | 0.7% | **45.1%** | **4.03** | **yes** |
| 25% | 17.0% | 2.0% | 30.8% | 2.86 | **yes** |
| 40% | 65.3% | 2.3% | 22.1% | 2.02 | **yes** |
| 60% | 92.3% | 8.0% | 17.2% | 1.48 | no |
| 80% | 95.3% | 12.7% | 14.1% | 1.19 | no |
| 100% | 98.0% | 9.3% | 12.7% | 1.00 | no |

**Recalibration fixes the validity failure and does nothing for the subgroup
failure.** At the mix an operator actually faces, a freshly recalibrated
pooled rule still runs the lowest-income band at **45.1%** against a 20%
budget, at **4.03×** its share — statistically indistinguishable from the
stale rule's 45.7% and 4.12×. The thing recalibration fixes is not the thing
that was broken.

> The fix is **calibrate per group**, not **recalibrate often**. Recalibrating
> is still worth doing; it is an answer to a different failure.

The concentration does fall at the right of that table, and for a reason that
is not a reassurance: when one band is 80% of the cases there is barely a
disparity left to have. At 100% it is 1.00 by definition.

**G1 missed.** I predicted recalibration would return violations to at or
below δ = 0.05 *at every* shift level. It does at the first three and not the
last three — 8.0%, 12.7%, 9.3%. The likely cause is the harness rather than
the method: forcing a band that holds 96 distinct cases up to 80% of a fold
requires resampling with replacement, so the calibration fold at those points
is built from few distinct cases and its exchangeability with deployment is
weakened by the resampling itself. **That is an explanation, not an excuse,
and the prediction is recorded as missed.**

**G2 held.** Group conditioning's coverage advantage shrinks from **+38.4
points** to a steady **+3.7 to +4.0** once the pooled rule is allowed to
recalibrate. Most of the stale advantage really was staleness, and saying so
is more useful than the larger number. Two sanity checks inside that: at a
100% share the two schemes are *identical* (87.3% each), because one band is
one group; and at 80% group conditioning is infeasible in all 300 trials, which
is reported as *never certified* rather than as zero coverage.

### What this does not show

That the method is safe under shift. It is not, and the table is how unsafe.
And group conditioning's invariance is narrow: it covers a shift in the
*proportions* of groups calibrated separately, and nothing else. A shift
*within* a band, a band calibration never saw, or a change in the relationship
between score and determinability breaks it exactly as they break the pooled
rule. Weighted conformal methods for covariate shift exist; none is implemented
here.

One limitation of the harness itself: forcing a 14.3% band to 80% of the fold
requires resampling it with replacement, so the right-hand rows rest on fewer
distinct cases — 14.3% distinct at full shift. That figure is reported per row
in the evidence rather than left for the reader to work out.

---

## Four bugs, all in the method's favour

Worth its own section, because the pattern is the point: **every defect found
by scrutiny made the method look better than it was**, and none was found by
the experiment that was supposed to validate it.

This section said "three" for several rounds while the opening said four, and
the fourth — the one below that scored a pre-registered prediction against a
measurement of the wrong thing — was described only in a docstring. A count
that disagrees with itself inside one document is the cheapest possible way to
lose a reader, and it survived because no test compared the two.

### The refusal threshold was not a refusal

When no threshold achieves the tolerance, calibration reports infeasible and
falls back to the most conservative threshold available. That fallback was
`1.0`. The rule commits on `score >= threshold`, so 1.0 is cleared by any score
reaching the top of its range — and **a score clipped into [0, 1] has a point
mass at exactly 1.0 by construction.** Under the anti-correlated score, 796 of
1,264 states sat at 1.0 and 792 of those were undecidable. The rule declined to
certify itself and then committed blind on nearly all of them: 100% of trials
violated.

It survived because `handcrafted_scorer` tops out at **0.9718** here, so the
sentinel was unreachable for the only scorer ever used.
`evaluate.ask_everything` had used `1.1` for this exact reason since the day it
was written — one part of the codebase knew and the fallback did not. And
`tests/test_rule.py` asserted `threshold == 1.0`: **the test suite was holding
the bug in place.**

### The subgroup comparison was measuring itself

`evaluate_by_group` used one parameter for two jobs — which threshold a case is
judged against, and how results are broken down. Under the pooled scheme there
is one calibration group, so results bucketed by it gave **one bucket**: the
"worst group" rate returned the pooled rate and concentration was 1.00 by
definition.

The table read: pooled worst group 11.1% and concentration 1.00, against
12.9% and 1.80 for the grouped rule — **group conditioning looking worse on
exactly the axis it was built to improve.** The real pooled figure, measured on
bands, is 45.7%. The partitions are separate arguments now, and a comparison
between schemes is only a comparison if every scheme is scored against the same
partition.

### The guarantee was conditional on feasibility and the metric was not

The procedure either issues a threshold that holds α or reports that none
does. Scoring a *declined* trial against a bound the method refused to issue
measures obedience to the flag, not the bound. Invisible while every condition
was feasible; load-bearing once corruptions made the procedure decline in 100%
of trials, where the honest statement is that there is no guarantee to test —
not that it held, and not that it failed. Reported as `None`, never `0.0`.

### A pre-registered prediction was scored against the wrong measurement

The worst of the four, and the last to be written up here. `validate_groups`
had no way to refit a scorer per trial. Addendum two asked whether group
conditioning fixes the subgroup failure **for a learned scorer** — H4 — and
with no refit available, that arm passed `handcrafted_scorer` to every row.

The table it printed looked like an answer to H4. It was a **duplicate of an
earlier round's scheme comparison**, and the learned scorer never appeared in
it. H4 was scored *held* on it. Nothing failed, nothing warned, and the arm
that was supposed to carry the prediction was not in the experiment.

**A missing capability that quietly changes which question is answered is
worse than one that raises an error.** `refit` exists now and
[`group.py`](src/abstain/group.py) carries the account beside it; H4 was
re-scored on the arm that actually varies the scorer, and holds — 86.5% → 7.0%
— which is the result the first table claimed without measuring.

One further defect does not belong in this list because it did not flatter the
method, only hide it: `robustness.noisy` seeded its generator from `hash()`,
which Python salts per process, so the corruption study was not reproducible
across runs. Three subprocesses gave three different answers. It now seeds from
SHA-256 of the state. Reported here because "every defect flattered the method"
is a claim about these four, and leaving out a fifth defect of a different kind
would make that claim look tidier than the record is.

Each fix kept its pre-fix run in `evidence/` rather than overwriting it. Fixing
a bug and re-running is not tuning, and the difference is only credible if both
runs survive.

---

## The original result, and its replication

### Validation found two failures before the holdout was opened

**Leakage, as expected.** A scorer fit on the whole pool then validated on
splits of that pool violated a 5% target in **40%** of trials. Refitting on a
disjoint fold cut it to **11%**.

**The agent's own stopping rule breaks exchangeability.** The remaining 11% was
not leakage. Calibration observed every knowledge state uniformly; the rule
commits at the **first** state to clear the threshold, which is selected by
construction. At a threshold of 0.82:

| | States | Undetermined |
|---|---:|---:|
| Calibration population | 1,264 | **80.3%** |
| States the rule visits | 314 | 57.0% |
| States it **commits at** | 55 | **0.0%** |

**This is the same failure `knowing-when-to-doubt` measures when a human
reviewer routes on model confidence — there the router is a person, here it is
the rule itself, and the mechanism is identical.** Making the calibration unit
the deployment unit takes violations to **0%**, at the cost of calibrating on
cases rather than states, which loosens the finite-sample bound.

### The holdout, opened once

**81 cases, 150 trials per tolerance.** Seven of eight pre-registered
predictions held.

| α | Violations | Infeasible | Coverage | Questions/case |
|---:|---:|---:|---:|---:|
| 0.20 | 1.3% | 0% | 81.5% | 2.18 |
| 0.15 | **5.3%** | 0% | 80.2% | 2.26 |
| 0.10 | 3.3% | 0% | 75.3% | 2.37 |
| 0.05 | — | **100%** | — | — |

**P2 missed:** 5.3% against a 5% target at α = 0.15 — 0.3 points over, 0.19
standard errors at 150 trials. Consistent with noise and still a miss, and
calling it one is cheaper than explaining it away. A test pins the miss so a
later edit cannot quietly drop it.

**Coverage rose from dev to holdout, 70.0% → 75.3%.** A method tuned against
its development set degrades on unseen data. This did not.

### Replicated on eight times the data

The household space is finite — 10 incomes × 4 × 4 × 4 = **640 households** —
so the original 160-case benchmark was a sample of a quarter of one grid.
Refining income to every 3,000 gives 21 values and **1,344 households, all of
which are built**: the complete enumeration, not a sample. Every original
income value is a multiple of 3,000, so the coarse benchmark is a **subset** of
this space — the same population at a different resolution, which is what makes
this a replication and not a change of subject.

Split 672/672, seed 20261008, `policyengine-us==2.33.0` recorded in the data.
**400 trials, fresh split, pooled rule:**

| α | Violations | Infeasible | Coverage | Questions/case |
|---:|---:|---:|---:|---:|
| 0.20 | **1.5%** | 0% | 76.0% | 2.06 |
| 0.15 | **0.0%** | 0% | 78.4% | 2.15 |
| 0.10 | **0.0%** | 0% | 77.2% | 2.27 |

α = 0.10 is now feasible in **100%** of trials where α = 0.05 was infeasible in
all of them on the coarse benchmark. The binding constraint was always sample
size, exactly as the power analysis says.

### The scorer I excluded was better

The pre-registration named the handcrafted scorer primary, reasoning that it
needs no fitting fold. Measured on holdout, refit per trial on a disjoint fold:

| Scorer | α | Violations | Coverage |
|---|---:|---:|---:|
| Handcrafted | 0.10 | 2.0% | 74.8% |
| **Fitted** | 0.10 | **1.0%** | **97.7%** |

**The judgement was wrong**, and the pre-registration is what preserves the
evidence that it was made in advance. One detail worth more than the result:
the two score almost identically on ordering — **AUC 0.9644 against 0.9631.** A
one-point AUC difference producing twenty-three points of coverage means the
ordering that matters is entirely local to the threshold.

**That is one of five independent results here saying AUC cannot see what this
method does.** Any one is a curiosity; together they are a claim about the
metric, so all five are listed in one place:

1. **A one-point AUC gap producing twenty-three points of coverage** — 0.9644
   against 0.9631, the table immediately above. The ordering that matters is
   local to the threshold.
2. **A corruption that leaves AUC identical to the floating-point bit** —
   `sharpen` is strictly monotone, so AUC and Kendall's τ are unchanged, and
   the deployed threshold and coverage are not.
3. **Per-band AUC of 0.9345 to 0.9976 while one band absorbs 4.1× its share of
   the budget** — near-perfect ranking *inside* the group the rule fails on.
4. **The scorer with the worst AUC of three has the best pooled safety and the
   best coverage** — 0.8888, and it wins on both axes the rule optimises. The
   first of these that points backwards rather than merely failing to
   discriminate.
5. **Three scorers spanning 0.9425 to 0.9604 produce deployed behaviour
   identical under `==`** — [above](#a-fifth-and-the-one-that-should-change-how-these-things-are-measured).
   AUC moved in both directions while nothing moved at all, which is worse
   than pointing backwards: it moved when there was nothing to see.

A test counts that list and requires every mention of the number elsewhere to
match it, because this count said "third", then "four", and was stale both
times — including inside the test that was pinning it.

---

## What is guaranteed, and on what basis

Four claims resting on different things, listed in the order
[`docs/theory.md`](docs/theory.md) separates them — and the four bullets below
were already four while this sentence said three, which is the arithmetic a
reader checks first.

**The Clopper–Pearson bound is exact** for a threshold fixed in advance. Not
novel, not in doubt.

**The calibration unit must match the deployment unit** — measured, mechanism
identified.

**The deployed rule holds its tolerance — empirically supported, not proved.**
Calibration searches 101 thresholds and reports the bound at whichever it stops
on; that bound is valid marginally for a threshold fixed in advance. The
construction does not deliver the statement, repeated validation does, and the
difference is worth keeping visible. A union bound over the grid restores a
provable simultaneous statement and roughly triples the data requirement —
`correct_for_search=True` turns the proof on for anyone who has it.

**And the guarantee is marginal, not conditional.** That is at the top of this
README rather than the bottom, because on this benchmark it is the difference
between a 98.5% pass rate and a 98.2% failure rate.

---

## How much data does any of this need?

[`src/abstain/power.py`](src/abstain/power.py) answers this in closed form,
before data is collected rather than after. Group-conditional safety at
tolerance α and confidence δ needs, **per group**:

| α | calibration cases | deployment cases | benchmark (smallest group at 14.3%) |
|---:|---:|---:|---:|
| 0.20 | 14 | 22 | 327 |
| 0.15 | 19 | 40 | 444 |
| 0.10 | **29** | **89** | **890** |

This exists because round three ran the subgroup experiment on 79 cases and
produced noise: ~11 calibration cases per band, where the bound at zero
failures is still 23.8%, and ~8 deployed cases per band, where a rate moves in
steps of 12.5 points and the question "did this band exceed 10%?" has no
answer. **The underpowered experiment reported no hidden subgroup. There was
one, at 45.7%.**

A failing test found a design defect while this was being written: the 60/40
calibration share is tuned for pooled validation, and group conditioning
inflates the **deployment** requirement far harder, so the wrong share costs
1.7× the cases. Round four uses 0.30, chosen from the requirement before the
data was split.

---

## If you are building one of these

Nine things this project measured that would have changed how I built it, in
the order they would bite.

**1. Check whether your error budget is spent evenly before you ship the
number.** It takes one breakdown by whatever groups your deployment actually
has. Here the pooled rate was inside budget in 98.5% of trials and some group
was outside it in 98.2%, and nothing in the headline number hinted at that.

**2. The check is only as good as the partition, and two groups is not a
partition.** Nine groupings of the same trajectories: a neutral equal-count
quartile split still flags the failure at α = 0.20, and a two-band split at the
median reports **no hidden subgroup at all**, at either tolerance. Same runs,
same rule, opposite conclusions. "We looked at subgroups" is not a finding
without saying which, and a coarse split is the one that will tell you what you
hoped to hear.

**3. Count failures per deployment, not just rates across deployments.** The
same arm, at α = 0.15: worst-band rate pooled across 200 trials, 11.65% against
a 15% budget — and **24.5% of individual trials** put some band over it. Both
numbers are correct. I published the first as "every band inside the budget"
and it was false of a quarter of deployments. This is the third time in this
repository that the unit of aggregation decided the answer.

**4. Do not pick the scorer by AUC.** Five independent results here show it
cannot see what a threshold-local rule does. One has it pointing backwards —
of three scorers, the one with the **worst** AUC had the lowest unsafe rate and
the highest coverage — and one has it moving in both directions across three
scorers whose deployed behaviour is identical in every float. Compare
candidates on the deployed metric at the deployed tolerance, not on a ranking
summary.

**5. Look for a feature that is directionally wrong for a group before you
reach for anything else, and then do the other thing as well.** Dropping the
one feature that read "far below the income limit" as "safe to answer" cut the
subgroup disparity from 4.13× to 1.72× and improved pooled safety and coverage
at once. It is the cheapest intervention measured here and the only one still
available at a tight tolerance. It is **not** a substitute for per-group
calibration: on the per-trial measure it matches conditioning at α = 0.20 and
is three times worse at α = 0.15, while the two together beat either alone
wherever both are feasible. I wrote that it beat every alternative; that was
one estimator's answer, not the answer.

**6. Calibrate per group if you can afford it, and do not expect recalibrating
to substitute.** On this benchmark conditioning was not a safety–coverage
trade — safer in every group, higher coverage, fewer questions. And a freshly
recalibrated single threshold still ran the worst group at 45.1% against a 20%
budget, essentially unchanged from a stale one: **recalibration fixes a
different failure.** The cost is sample size, and it is a hard floor —
`1 − δ^(1/n) ≤ α` must hold **in your smallest group**, which is 29
calibration cases for a 10% tolerance at 95% confidence, whatever your scorer.

**"If you can afford it" is doing real work in that sentence.** At α = 0.10 on
672 cases, conditioning is feasible in **3 trials out of 200** for the
handcrafted scorer and **0 of 200** for the better-behaved one — so at that
tolerance the per-group certificate is not expensive, it is unavailable, and
the only thing left is a score that does not need it. Decide which tolerance
you are actually buying before you decide how.

**7. Size the deployment fold, not just the calibration fold.** The default
60/40 split is tuned for a pooled check. A per-group rate has to be
*resolvable* in every group, and that requirement grows much faster — the
wrong split cost 1.7× the cases here, and a rate measured on 8 cases cannot
answer whether a group exceeded 10%.

**8. Make "infeasible" actually infeasible, and report it as its own
outcome.** The refusal threshold has to be outside the score's range, not at
the top of it. And a declined calibration is neither a pass nor a failure:
pooling it with real trials hides the difference between "held", "broke" and
"never certified".

**9. Watch the deployed rate, not the certificate.** The bound is computed on
calibration data. When the population shifted here, the reported bound stayed
at 0.175 while violations went from 0.7% to 98%. **An operator monitoring the
guarantee would have seen nothing.** If you can only monitor one number,
monitor the realised rate on recent decisions — broken out by group, because
the pooled realised rate is the number that was already hiding a 45% group.

And the thing that most needs doing next and is not done here: **run it on a
language model's own confidence.** The corruption study brackets the answer —
safe but possibly useless — and brackets are not measurements.
[`src/abstain/model.py`](src/abstain/model.py) is the harness for it, tested
against a scripted transport and never run against a model, so what is missing
is a key rather than a design.

It encodes one requirement that is easy to get wrong and fatal if you do:
**the score has to be a function.** The rule evaluates the same state more
than once — the question selector looks ahead, then the stopping rule scores
where it landed — so a scorer that calls the API each time returns different
numbers for the same state, and any violation is then attributable to the
non-determinism rather than to the score. Every call is cached on the state,
and the cache is what makes it a function; `temperature=0` is set too and is
the weaker guarantee, since providers do not promise determinism at zero.

## The case against

[`docs/against.md`](docs/against.md) lists the objections, leading with the one
that cannot be fully answered: **no language model was run.** The rule is
evaluated against an oracle-backed simulation where determinability is
computable, and the deployment it is motivated by is one where it is not. The
corruption study above is the nearest honest substitute and it is a substitute.

The companion benchmark measured a real model answering **62.5%** of
undecidable cases. That number and these are **not comparable** — different
cases, different n, free text rather than four known fields. Putting them in
one table would be the most misleading thing this repository could do, so it
does not.

---

## The holdout is locked before the method exists

The failure mode of a method paper is tuning against the evaluation until it
wins. It is rarely deliberate — it happens one reasonable decision at a time.

So the split is the **first commit**, and the git history is the evidence that
it precedes every line of method code.

| Benchmark | dev | holdout | Status |
|---|---:|---:|---|
| Coarse (sample of the 640-household grid) | 79 | 81 | opened twice; the record of the original result |
| **Fine (complete 1,344-household enumeration)** | **672** | **672** | holdout opened once, for round four |

Each half ships a SHA-256 and `tests/` asserts the committed digests still
match. **An independent machine has since reproduced them**: the build
workflow fired on an unrelated push, rebuilt the coarse benchmark from
scratch, and — because the version pin landed in a later commit — did it
under `policyengine-us==2.33.1` against the 2.33.0 the data was built with.
The digests came out byte-identical, which makes the reproducibility claim
demonstrated rather than asserted and shows the determinability verdicts
stable across at least one patch release of the oracle. It does not retire
the pin: stable across one patch release is not stable across any version. `split.py` later grew options so the second benchmark could reuse its
stratification; because that file is the first commit, its evidence is
converted from *untouched* to **verified identical** — the test suite re-runs
the default call and digests it against the values committed originally. They
match exactly.

Holdout access is guarded by test, one guard per benchmark. The guard used to
match any filename containing `holdout.json`; when the second benchmark arrived
it fired on a document that never touches the first, because it could not tell
them apart. Loosening it to pass would have left **both** holdouts unguarded,
so it was split in two instead.

**A result on dev is a demonstration. A result on holdout is a result.**

Five pre-registrations, each committed before the code it needed existed:
[one](docs/preregistration.md) ·
[two](docs/preregistration-2.md) ·
[three](docs/preregistration-3.md) ·
[four](docs/preregistration-4.md) ·
[five](docs/preregistration-5.md)

## Reproducing any of it

No dependencies beyond the standard library to *run* the method — the
logistic regression is written out, the binomial bound is written out, and the
figure is hand-built SVG. PolicyEngine is needed only to rebuild the
benchmark, and the committed benchmark means you do not have to.

```bash
pip install -e ".[dev]"
pytest -q                               # ~170 tests, including every claim
                                        # in this README checked against the
                                        # evidence file that produced it

python scripts/run_secondary.py         # rounds 2-3: plug-in baseline,
                                        # corruptions, conditional coverage
python scripts/rerun_corruption.py      # round 2 after the sentinel fix
python scripts/run_round4.py --set dev  # replication + schemes, dev
python scripts/run_round5.py            # per-band detail + the shift sweep
python scripts/run_recalibration.py     # does recalibrating alone fix it?
python scripts/run_allocation.py        # questions per band, per scheme
python scripts/check_confounds.py       # is it the stopping or asking rule?
python scripts/diagnose_mechanism.py    # why the levels are shifted
python scripts/run_plugin_scale.py      # does the baseline fail at scale?
python scripts/run_materiality.py       # how much rides on the $50 parameter?
python scripts/run_uncertainty.py       # cluster bootstrap over cases
python scripts/make_figure.py           # regenerate docs/shift.svg

# Rebuilding the benchmark needs the pinned oracle, and takes ~12 minutes.
pip install "policyengine-us==2.33.0"
python scripts/build_cases.py --n 1344 --seed 515 --fine-incomes \
    --out evidence/cases_fine.json
python scripts/split.py --source cases_fine.json --prefix fine_ \
    --seed 20261008
```

Every script writes its numbers to `evidence/` and prints the same table it
writes. Seeds are fixed in the scripts, not passed on the command line, so a
rerun is the same run.

`scripts/run_round4.py --set holdout` is deliberately not in that list. It
opens the fine holdout, which has been opened once.

## Status

Built, validated, replicated, and reported including every prediction that
missed, every judgement that was wrong, every bug that flattered it, and the
one central claim that its own pre-registered test refuted.

**The confirmatory holdout run was interrupted partway through** by the
session it was running in, after the replication and concentration tables had
printed. It was relaunched rather than re-designed: the seed is fixed in the
script, the script's last commit predates the first run, and nothing between
the two touched the benchmark — so a resumed run is the same draw, not a
second look. That claim is checked rather than asserted.
[`scripts/verify_resumed_run.py`](scripts/verify_resumed_run.py) requires
every numeric row the interrupted log printed to reappear character for
character in the completed one, and the interrupted log was committed
*before* the relaunch so it could not be edited to match afterwards. If a
single number had moved, the two would be different experiments and the
result would be discarded rather than explained.

## License

MIT. Derived from the `underdetermined` benchmark in the same account.
