# What is guaranteed, and on what basis

Four claims appear in this repository. They rest on different things and are
separated here because conflating them is the easiest way to overstate the
result.

The fourth was added after it was measured, and it is the one that most
changes what the method is for: **the guarantee is marginal, and on this
benchmark the gap between marginal and conditional is the difference between a
98.5% pass rate and a 98.2% failure rate.** It is §4 rather than a note under
"what none of this covers", because a caveat that large is not a caveat.

---

## 1. The Clopper–Pearson bound is exact

For a threshold **fixed in advance**, with `k` unsafe commitments out of `n`,

> P(true unsafe rate > CP_upper(k, n, δ)) ≤ δ

This is a standard exact binomial interval. Nothing here is novel and nothing
here is in doubt. It is why the threshold is chosen against the bound rather
than against the empirical rate — a threshold tuned to hit α on the sample
sits above α half the time.

**Status: proved, and not by me.**

## 2. The calibration unit must match the deployment unit

Calibrating over knowledge states uniformly and deploying under a rule that
commits at the first state to clear the threshold breaks exchangeability. At
a threshold of 0.82 on dev:

| | States | Undetermined |
|---|---:|---:|
| Calibration population | 1,264 | 80.3% |
| States the rule visits | 314 | 57.0% |
| States it commits at | 55 | 0.0% |

### The evidence for this claim was wrong, and the claim survives in a sharper form

What this section said until round S:

> ~~Measured consequence: 11% of trials violated a 5% target, with the scorer
> refit on a disjoint fold so leakage is excluded. Calibrating on commitments
> instead takes it to 0%.~~

**Retracted.** Both figures came from `evidence/leakage.json` and
`evidence/unit_comparison.json`, added at commit 6 — and the fix for this
repository's third bug, `violation_rate_when_feasible`, landed at commit 13.
Those files report violations **pooled over trials the procedure declined**,
which is the exact defect the README documents, in evidence that predates its
fix. Read off the old files:

| the figure | what it actually was |
|---|---|
| 11% violated a 5% target | 11 of 100 trials, of which **76 were infeasible** |
| commitments take it to 0% | zero violations in **100% infeasible** trials |

The second is the vacuous zero the bug-3 fix exists to prevent, sitting inside
a numbered claim. And the sentence compared two different experiments — 100
trials against 80 — as though they were two arms of one.

Worse for the record: **neither file was written by any script**, so neither
could be regenerated, and **no test read them**, so the figure-coupling
discipline never reached them. So the 11% is not restated below, only
retracted — the original fold construction is not recoverable, which makes a
re-run a new experiment rather than a correction.

### What a clean run shows instead

`scripts/rerun_unit_and_leakage.py`, dev's 79 cases, scorer refit per trial,
the feasibility-conditioned metric:

| unit | α | certified | violated **when certified** |
|---|---:|---:|---:|
| state | 0.10 | 80 of 80 | **0.0%** |
| trajectory | 0.10 | 58 of 80 | 5.2% |
| **state** | **0.05** | **12 of 80** | **75.0%** |
| **trajectory** | **0.05** | **0 of 80** | — |

At α = 0.10 both units hold. At α = 0.05 the difference is not a violation
rate at all:

> **Using the wrong unit does not bias the estimate. It manufactures
> feasibility.** Calibrating over states gives ~1,264 calibration points
> against the trajectory unit's ~47, so its Clopper–Pearson bound clears
> easily — and the bound is on the wrong population. It issues a 5% threshold
> in 12 trials and the deployed rate breaks it in **nine of those twelve**.
> The trajectory unit finds that no threshold achieves 5% on 47 commitments,
> which is true, and declines in every trial.

That is a stronger claim than the one it replaces, and the reason is worth
stating: **a procedure that declines is not a procedure that failed.** The
honest comparison is between a unit that certifies what it cannot deliver and
one that refuses, not between two violation rates.

**Status: measured, after the first measurement was retracted. The mechanism
is the one `knowing-when-to-doubt` identifies for human routers** — the
agent's stopping rule plays the role the reviewer plays there — and the
feasibility arithmetic is the one [`power.py`](../src/abstain/power.py) gives
in closed form: 47 commitments cannot certify 5% at δ = 0.05, and no amount of
implementation care changes it.

## 3. The deployed rule holds its tolerance

This is the claim the method advertises and **it is not proved.**

`calibrate_on_trajectories` searches 101 thresholds and reports the bound at
whichever it stops on. The bound is valid marginally, for a threshold fixed in
advance, and this threshold is selected using the data the bound is computed
on. The construction therefore does not deliver the statement.

### What supports it instead

Repeated validation. Fresh calibration and deployment sets, disjoint, 150
trials per tolerance:

| | α = 0.20 | α = 0.15 | α = 0.10 |
|---|---:|---:|---:|
| dev | 2.0% | 1.3% | 1.3% |
| **holdout** | **1.3%** | **5.3%** | **3.3%** |

Pre-registered before the holdout was opened; seven of eight predictions held
and the miss (5.3% against a 5% target, 0.19 standard errors) is recorded as
a miss.

**Status: empirically supported, not proved. That is weaker and it is what
the evidence is.**

### The provable version, and what it costs

A union bound over the grid — testing each candidate at δ/101 — restores a
valid simultaneous statement. Measured on dev it is unaffordable here:

| α | Violations | Infeasible | Coverage |
|---:|---:|---:|---:|
| 0.20 | 0.0% | **55%** | 66.5% |
| 0.15 | 0.0% | **100%** | — |
| 0.10 | 0.0% | **100%** | — |

Because the requirement roughly triples:

| Target α | Cases for the marginal bound | Cases for the simultaneous bound |
|---:|---:|---:|
| 0.20 | 14 | 35 |
| 0.15 | 19 | 47 |
| 0.10 | 29 | **73** |
| 0.05 | 59 | **149** |

The calibration fold here is 47 cases. So α = 0.10 is affordable marginally
and not simultaneously, by about a factor of three.

**The proof is available to anyone with three times the calibration data, and
`correct_for_search=True` turns it on.** Nothing about the method changes —
only the level each candidate is tested at, and how much data is required to
pass.

---

## 4. The guarantee is marginal, not conditional

§1 to §3 are statements about the error rate **over the population**. None of
them says anything about any subgroup, and that is not a gap in the argument —
it is what the argument is. Achieving conditional coverage without
distributional assumptions is known to be impossible in general, so a
distribution-free marginal bound is the correct thing to have proved.

The question is whether the distinction matters here. It does, more than
anything else in this document.

**Measured on 672 cases, 400 trials, α = 0.20:**

| | |
|---|---:|
| Trials honouring the budget **overall** | **98.5%** |
| Trials breaking it **for some income band** | **98.2%** |

| band | deployed | unsafe rate | share of budget / share of cases |
|---|---:|---:|---:|
| **well-below** | 26,752 | **45.7%** | **4.12×** |
| near-threshold | 53,916 | 5.2% | 0.47× |
| above | 35,934 | 5.6% | 0.50× |
| well-above | 71,798 | 5.4% | 0.49× |

Those figures carry a cluster bootstrap rather than a binomial interval,
because the 26,752 observations are **96 distinct households** deployed once
per trial. A standard error from 26,752 would claim ±0.6 points; resampling
cases gives ±9.5. The conclusion is unchanged — the lower bound is 39.9%
against a 20% budget — and the width is reported so a reader is not quietly
given sixteen times more precision than the design supports.

#### And the 98.2% carries its own width, which is the smaller surprise

The pair at the top of this section is a **per-trial** rate, and for a long
time it was quoted with no interval at all. It has two now, measuring
different things, and the gap between them is much smaller than the one above:

| | point | pool-level 95% | exact, this pool | widening |
|---|---:|---|---|---:|
| one global threshold | 98.2% | [94.0%, 100.0%] | [94.6%, 100.0%] | **1.11×** |
| one per band | 5.1% | [1.0%, 11.1%] | [1.1%, 10.2%] | **1.11×** |

The exact interval is Clopper–Pearson over trials, which is correct
*conditional on these 672 cases* — each trial is an independent split of a
fixed pool. The pool-level interval resamples the 672 cases themselves, 40
bootstrap pools of 100 trials each, and **widens the result by eleven
percent.**

Eleven percent, where the same operation on the band rates above widened them
**sixteenfold.** That contrast is the point:

> A per-trial rate averages over the **whole pool** in every trial. A per-band
> rate is driven by the **96 cases in one band.** Resampling 672 cases barely
> moves the first and dominates the second.

So the two intervals are both honest and neither is the right one to quote in
general: **the unit of aggregation has to be matched to the quantity.** Here
that licenses quoting the per-trial figures as they stand, and it licenses
nothing about any per-band number, where the narrow interval remains
indefensible.

All five of round R's predictions held, which makes it the only clean round in
the ledger, and the comparison above is worth more than the five passes. Run,
seeds and scoring: [`preregistration-5.md`](preregistration-5.md) addendum ten
and `evidence/pool_bootstrap.json`.

### The mechanism, and the version of it that was refuted

Per-band AUC is 0.9345 to **0.9976** — the scorer orders states almost
perfectly *inside the band it fails on*. What differs is the score **level**:
undecidable states average 0.2106 in `well-below` against 0.1131 in
`near-threshold`. One global threshold is a single horizontal line across four
vertically shifted distributions, so it cuts each at a different quantile.

> Good ranking within every subgroup does not give a threshold that is safe
> within every subgroup. Conditional validity needs conditional
> **calibration**, not conditional ranking.

And the reason the levels are shifted is sharper than a bad feature. The
scorer estimates whether **eligibility** is settled; determinability here
requires the **award** to be settled too. Far below the income limit
eligibility is clear and the award swings hardest with household size, so the
scorer is confident, correct about its own question, and wrong about the one
it is scored on — and the two questions diverge most exactly where income is
lowest.

Measured two ways. Of the states the rule actually commits on while
undetermined, **72%** of `well-below`'s are award-only against 0% of
`above`'s. And re-labelling the benchmark so determinability means eligibility
alone drops the concentration from **4.07 to 1.55**. Across materiality
thresholds from $0 to $500 it does not move at all, so none of this is a
property of where that threshold was set.

#### What this section claimed for two rounds, and why it was wrong

> ~~It is a property of using one threshold rather than a property of this
> scorer. A better-ranking scorer does not fix it.~~

**Refuted by its own pre-registered test (J1).** A scorer refit without the
distance feature cuts the concentration from **4.13 to 1.72** and puts every
band inside the budget **on the across-trial estimator** — a qualification
round O added, and it matters: on the per-trial measure the same arm breaks
the budget for some band in **24.5%** of trials at α = 0.15. The strong form
of the claim does not survive either way, and this document carried it after
the README had already recorded the refutation — a stale claim in the theory
file is worse than one in a write-up, because this is the document a reader
checks the write-up against.

What survives, and it is narrower:

> The concentration is driven **primarily by a score feature that is
> systematically wrong for one group**, and a single threshold cannot absorb
> that. It is not an artefact of the hand-built functional form — learning the
> weights over the same features leaves **3.31**. Removing the feature shrinks
> the disparity 2.4× and does not eliminate it: the same band is still worst
> at **1.72×** its share.

So a single threshold contributes and here it is not the dominant term.

#### And the feature-level repair does not work either

The diagnosis implies a fix: add a term for how much the award could move.
Two were pre-registered and built — `award_aware_scorer`, then
`signed_scorer`, which applies the term only below the boundary so that it
reorders states rather than rescaling them. Both failed, and the way they
failed is the most transferable result here.

| | AUC | reachable pairs reordered | immediate commits at τ = 0.3 |
|---|---:|---:|---:|
| handcrafted | 0.9555 | — | 225 |
| award-aware | 0.9425 | 4.77% | **0** |
| signed | **0.9604** | 3.04% | 129 |

Three different functions, and **one policy**: pooled 11.29%, `well-below`
45.93%, coverage 76.04%, 2.0525 questions per case, concentration 4.0691 —
identical under `==` for all three, at both tolerances, including the
group-conditional arms.

Both terms are gated on `dependents` being unknown, and the greedy selector
asks for `dependents` first in **all 447 cases that ask anything**. The terms
act on the opening state and nowhere else; an agent that does not commit
immediately asks the one question that switches them off.

> **In a sequential rule, a caution term conditioned on an unknown is defeated
> by the agent resolving that unknown.** And a confidence function for such a
> rule cannot be evaluated on the state space — only on the states the agent
> reaches under the rule. AUC moved by 0.0179 in both directions while
> behaviour did not move in any digit.

#### Which remedy, measured on the estimator that counts failures

Three remedies, and the comparison depends on which estimator is used — which
is itself the finding. Trials in which **some** band exceeded α, out of 200:

| α | handcrafted + conditioning | no-distance, one threshold | both |
|---:|---|---|---|
| 0.20 | 2.6% [0.8, 5.9], 196 feasible | **2.5% [0.8, 5.7]**, 200 | **1.1% [0.1, 3.8]**, 187 |
| 0.15 | **8.3% [4.1, 14.8]**, 120 | 24.5% [18.7, 31.1], 200 | **4.0% [1.1, 10.0]**, 99 |
| 0.10 | 0.0% **[0.0, 70.8]**, 3 | 26.0% [20.1, 32.7], 200 | — 0 |

Exact 95% intervals, and two cells need them. At α = 0.20 the first two
columns are **indistinguishable**, not a ranking. At α = 0.10 the leading cell
is zero failures in **three** trials with an upper bound of **70.8%** — it
supports almost nothing, and read as "conditioning is perfect there" it is the
opposite of the truth. The intervals are exact conditional on the 672-case
pool and do not cover the pool itself, so they are narrower than the
uncertainty an operator faces; `group.trial_rate_interval` says so in more
detail.

**Removing** the offending feature is the cheapest remedy and the best on
every *pooled* axis — 7.3% pooled unsafe, 92.7% coverage, worst band 12.5% —
while scoring the **worst** AUC of any arm, 0.8888. On the per-trial measure
it matches conditioning at α = 0.20 and is three times worse at α = 0.15.

**Conditioning** works without touching the scorer and is the only one of the
three that yields a *certificate* rather than an outcome. Its cost is sample
size and the cost is steep: 3 feasible trials in 200 at α = 0.10.

**Both together** beat either alone wherever both are feasible.

**Adding** the missing feature does nothing at all — see below.

At α = 0.10 on 672 cases **there is no remedy to buy.** Conditioning is
infeasible in every trial for both scorers, so a per-group guarantee is not
available at any price, and what remains is a better-behaved score whose
per-group behaviour is measured rather than guaranteed.

**Status: measured, and narrowed three times.** The subgroup failure is real,
the practical ordering is the reverse of the intuitive one — look for a
feature that is directionally wrong for a group before reaching for a better
one — and the two remedies are complements rather than substitutes.

### The fix, its status, and its cost

One threshold per band — Mondrian conformal prediction, not new here. Paired
on identical draws at α = 0.20:

| | violations per band | worst band | coverage | questions/case | infeasible |
|---|---:|---:|---:|---:|---:|
| one global threshold | 98.2% | 45.6% | 76.0% | 2.06 | 0% |
| **one per band** | **3.3%** | **12.9%** | **81.0%** | **1.89** | 2.8% |

**Status: measured. The guarantee it delivers is per-group at level δ**, which
is a stronger statement than §3's and rests on the same §1 bound applied
within each group — so its epistemic standing is §3's, group by group, with
the same unproved threshold-search step.

Its cost is not coverage. It was pre-registered as a coverage cost and that
prediction was wrong: a single threshold has to be high enough for the worst
band and is then too high for the other three, so the pooled rule was never on
the safety–coverage frontier. The cost is **sample size** — δ-level
feasibility in *every* group at once, so the smallest group binds. At α = 0.10
on 672 cases it is feasible in 7 trials out of 400, exactly as
[`power.py`](../src/abstain/power.py) predicted before the run.

### And recalibration does not substitute for it

The obvious alternative to conditioning is to recalibrate when the population
moves. Measured, with the calibration fold reweighted to the deployment mix,
at the natural band mix:

| | pooled rate | worst band | concentration | hides a subgroup |
|---|---:|---:|---:|:--:|
| stale threshold | 11.1% | 45.7% | 4.12 | yes |
| **freshly recalibrated** | 11.2% | **45.1%** | **4.03** | **yes** |

Recalibration restores the **marginal** guarantee — violations at a full shift
fall from 98.0% to 9.3% — and moves the conditional failure by less than a
point. **The thing it fixes is not the thing that was broken**, because the
concentration was never a staleness artefact: it is what one threshold does to
groups whose score distributions sit at different levels, and a freshly
computed single threshold is still a single threshold.

**Status: measured.** It also means the practical recommendation cannot be
softened to "recalibrate often", which would have been the cheaper advice.

### What conditioning does not fix

It is validity conditional on **the groups you chose**. A subgroup that cuts
across the bands is no better protected than before, and there is no finite
amount of conditioning that covers every subgroup — that is the impossibility
result again. `group.threshold_for` refuses to serve a group calibration never
saw rather than borrowing another group's threshold, which is the honest
behaviour and not a solution.

---

## What none of this covers

**Correctness.** The bound is on answering while undecidable. A case can be
decidable and the agent still wrong, and nothing here constrains that.

**Distribution shift.** Every validation in §1 to §4 draws calibration and
deployment from one pool, which is exactly the exchangeability the argument
assumes. Round five breaks it on purpose and prices it — calibrate on the
natural band mix, deploy on a mix shifted toward `well-below` — and the
results are in [`preregistration-5.md`](preregistration-5.md) and
`evidence/round5_shift.json`. The headline expectation, pre-registered, is
that **group conditioning is substantially robust to a shift in group
proportions and the pooled rule is not**, because re-weighting groups
calibrated separately changes which thresholds are used, not what any
threshold is.

That invariance is narrow and worth stating precisely. It does not cover a
shift *within* a band, a band calibration never saw, or a change in the
relationship between the score and determinability. Those break group
conditioning exactly as they break the pooled rule. Weighted conformal methods
for covariate shift exist and none is implemented here.

**The oracle.** Determinability comes from PolicyEngine, an implementation of
published rules with its own defects. Where it is wrong, this bounds agreement
with a wrong oracle. The version is recorded in the data
(`policyengine-us==2.33.0`) rather than left to the environment, because
determinability is defined by what the engine says — two builds under
different versions are two benchmarks.

**Anything a language model does.** No model was run. The corruption study in
[`results-secondary.md`](results-secondary.md) is the nearest substitute and
is a substitute.
