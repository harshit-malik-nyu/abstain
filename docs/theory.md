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

Measured consequence: 11% of trials violated a 5% target, with the scorer
refit on a disjoint fold so leakage is excluded. Calibrating on commitments
instead takes it to 0%.

**Status: measured, and the mechanism is the one
`knowing-when-to-doubt` identifies for human routers.** The agent's stopping
rule plays the role the reviewer plays there.

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

### The mechanism, which is not a scorer defect

Per-band AUC is 0.9345 to **0.9976** — the scorer orders states almost
perfectly *inside the band it fails on*. What differs is the score **level**:
undecidable states average 0.2106 in `well-below` against 0.1131 in
`near-threshold`. One global threshold is a single horizontal line across four
vertically shifted distributions, so it cuts each at a different quantile.

> Good ranking within every subgroup does not give a threshold that is safe
> within every subgroup. Conditional validity needs conditional
> **calibration**, not conditional ranking.

**Status: measured, and it is a property of using one threshold rather than a
property of this scorer.** A better-ranking scorer does not fix it; the fitted
scorer, which ranks better, would be subject to exactly the same argument.

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
