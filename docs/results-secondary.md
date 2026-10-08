# Rounds two to four

Three questions a reviewer asks first, and what happened when they were asked
properly. Each round was pre-registered before the code it needed existed:
[round two](preregistration-2.md), [round three](preregistration-3.md), [round
four](preregistration-4.md).

The short version:

- **Why not just pick a threshold?** Because the plug-in threshold violates
  its budget in 17–21% of trials where the conformal one violates in 0.7–3%.
- **Your scorer is a toy.** The bound holds under every corruption tested,
  including the exact negation of a good score. What degrades is coverage, and
  then feasibility. Two corruptions found a safety bug the primary experiment
  could not have found.
- **Marginal coverage hides subgroup failure.** It does, badly. At α = 0.20 the
  pooled unsafe rate is 11.1% and the lowest-income band's is **45.7%**. The
  first attempt to measure this said there was no problem; it was underpowered
  and the fix was an eight-times-larger benchmark.

Two of the three rounds found bugs in this repository rather than facts about
the world, and both bugs were in the direction of making the method look
better than it was.

---

## Round two, experiment A — the plug-in baseline

Identical pipeline, one line different. Both search the same pre-specified
101-point grid for the smallest threshold whose calibration unsafe rate is
within α. They differ only in what "within α" means: the method requires the
**Clopper–Pearson upper bound** at δ to be under α; the baseline accepts the
**empirical rate**.

The baseline is not a straw man. It is what a competent engineer writes when
asked to hold an error budget, and it is correct in expectation — which is
exactly why it fails. An operator who asks for 5% and gets 5% *on average* is
over budget half the time.

**Dev, 150 trials, calibration fold held at a fixed size, α = 0.10:**

| Calibration cases | Conformal | | Plug-in | |
|---:|---:|---:|---:|---:|
| | violations | infeasible | violations | infeasible |
| 40 | 3.3% | 28.0% | **16.7%** | 0% |
| 50 | 0.7% | 0% | **20.7%** | 0% |

The plug-in violates its budget three to four times as often as δ allows, and
it never reports infeasible — it always has a threshold to offer, and the
threshold is not safe.

**A1 held.** **A2 missed:** the violation rate did not rise monotonically as
calibration shrank; it was *higher* at 50 cases than at 40. The mechanism
predicted — small-sample optimism — is real but not monotone at this
resolution, and at 150 trials the difference between 16.7% and 20.7% is about
one standard error. Recorded as a miss.

**A4 held**, and it matters that it did: the plug-in's coverage is *higher*
(70.8% against 67.5% at 40 cases). The method buys safety with coverage, and
if the baseline had been worse on both axes the comparison would have been
measuring an implementation difference rather than a statistical one.

---

## Round two, experiment B — the bound under a bad score

`rule.py` claims the guarantee "does not depend on [the score] being good,
only on it being fixed before calibration." That is the conformal argument's
real content and it makes score quality a **coverage** question rather than a
**safety** one. It had never been tested.

Eight corruptions, each applied identically in calibration and deployment so
that exchangeability — the assumption — is held fixed while quality varies.

| corruption | AUC | Kendall τ | what it imitates |
|---|---:|---:|---|
| identity | 0.9511 | 1.000 | control |
| coarse(0.1) | 0.9463 | 0.981 | confidence clumping on round values |
| sharpen(0.25) | 0.9511 | **1.000** | overconfidence; strictly monotone |
| noisy(0.10) | 0.9414 | 0.755 | mild loss of ordering |
| noisy(0.25) | 0.9004 | 0.628 | moderate |
| noisy(0.50) | 0.7830 | 0.411 | severe |
| constant | 0.5000 | 0.000 | no information |
| inverted | 0.0489 | **−1.000** | the theory's worst case |

### The safety bug this found

**Predictions B1 and B4 failed on the first run.** Under `inverted`, 100% of
trials violated at every tolerance. Under `noisy(0.25)`, 63.3% at α = 0.15.

The cause was not the theory. When no threshold achieves the tolerance,
calibration reports infeasible and falls back to the most conservative
threshold available — and that fallback was **1.0**. The rule commits on
`score >= threshold`, so 1.0 is cleared by any score that reaches the top of
its range, and **a score clipped into [0, 1] has a point mass at exactly 1.0
by construction.** Under `inverted`, 796 of 1,264 states sat at 1.0 and 792 of
those were undetermined. The rule declined to certify itself and then
committed blind on nearly every one of them.

Three things about how it survived:

- `handcrafted_scorer` tops out at **0.9718** on this benchmark. The sentinel
  was unreachable for the only scorer the primary experiment ever used, so 150
  trials at four tolerances could not have found it.
- `evaluate.ask_everything` had used 1.1 for this exact reason since the day
  it was written. One part of the codebase knew and the fallback did not.
- `tests/test_rule.py` asserted `threshold == 1.0`. **The test suite was
  holding the bug in place.**

Fixed to the tightest float strictly above the documented range, pinned from
both ends: the sentinel is above 1.0, and a scorer returning exactly 1.0
everywhere is asserted to commit nothing at it. The pre-fix run is kept in
`evidence/secondary-prefix-run.txt` rather than overwritten.

### The result, after the fix

**Dev, 150 trials. Violations are over feasible trials — the guarantee is
conditional on feasibility and always was.**

| corruption | α | feasible | violations | coverage |
|---|---:|---:|---:|---:|
| identity | 0.20 / 0.15 / 0.10 | 150 / 150 / 150 | 2.0% / 0.7% / 0.7% | 72.9% / 73.5% / 70.8% |
| coarse(0.1) | 0.20 / 0.15 / 0.10 | 150 / 150 / 116 | 0% / 0% / 0% | 65.2% / 65.2% / 62.7% |
| sharpen(0.25) | 0.20 / 0.15 / 0.10 | 150 / 150 / 150 | 0% / 0% / 0% | 75.2% / 74.3% / 74.6% |
| noisy(0.10) | 0.20 / 0.15 / 0.10 | 76 / 25 / **0** | 3.9% / 12.0% / — | 40.4% / 38.8% / — |
| noisy(0.25) | all | **0** | — | — |
| noisy(0.50) | all | **0** | — | — |
| constant | all | **0** | — | — |
| inverted | all | **0** | — | — |

**Nothing violates. Everything degrades through coverage and then through
infeasibility** — the rule stops certifying itself rather than certifying
something false. That is the theory's claim measured rather than asserted, and
the worst case tested is the exact negation of a good score.

> The guarantee is a **safety** guarantee and not a **usefulness** guarantee,
> and on this benchmark the difference is 73% coverage against 0%.

### Two numbers that answer the objection `against.md` leads with

No language model was run here, and the corruption set is how that objection
gets a quantitative answer rather than a shrug. A model's self-reported
confidence clumps on round values and is imperfectly ordered, and both are in
the table:

- **Rounding to tenths alone costs 8 points of coverage** (72.9% → 65.2%) and
  makes a 10% tolerance infeasible in 23% of trials.
- **Mild rank noise — Kendall τ 0.755, a plausible description of model
  confidence — collapses coverage from 72.9% to 40.4%**, and a 10% tolerance
  becomes unreachable entirely.

So a conformal abstention wrapper built on a badly-ordered confidence signal
is safe and close to useless. That is worth knowing before building one, and
it is not what the theory's reassuring "any fixed score" suggests at first
reading.

### B2, the prediction written to discriminate

**B2 held, and it held informatively.** `sharpen` is strictly monotone, so the
ordering is identical to the floating-point bit (τ = 1.000 exactly). The rule's
stopping condition is a threshold comparison and should be blind to it — but
the pre-registration flagged in advance that `_default_choice` picks the next
question by the largest score **difference**, and differences are not
monotone-invariant.

Coverage moved by **+2.3, +0.8 and +3.8 points**. Non-zero, detectable,
inside the predicted 5-point band. The architecture is value-sensitive exactly
where predicted and only mildly, which is the outcome that distinguishes a
prediction from a safe bet.

### Two honest wrinkles

**B3 passes without testing what it was meant to test.** Coverage is monotone
in σ, but it reaches zero by infeasibility rather than by gradual degradation.
Read it as a near-miss.

**`noisy(0.10)` at α = 0.15 is 3 violations in 25 feasible trials — 12.0%.**
It passes only because the acceptance slack is computed from the *feasible*
trial count: at 25 trials the standard error is 4.4 points and the band
reaches 13.7%. That is a pass on almost no evidence, and the feasible count is
in the table so a reader can see it.

---

## Round three — the question that could not be answered

Experiment C broke the pooled unsafe rate down by income band, and **three
predictions missed at once.**

Predicted: the budget concentrates on `near-threshold`, where the unknown
fields move the verdict. Found, on the 79-case dev set at α = 0.20:

| band | deployed | unsafe | rate | concentration |
|---|---:|---:|---:|---:|
| well-below | 1,056 | 203 | **19.2%** | **3.44×** |
| near-threshold | 1,627 | 0 | 0.0% | 0.00× |
| above | 1,158 | 65 | 5.6% | 1.01× |
| well-above | 959 | 0 | 0.0% | 0.00× |

**The predicted band took none of it.** The band that absorbed 3.44× its
proportional share was `well-below` — the lowest-income households.

### The mechanism, which is not what it looks like

Not bad ranking. Per-band AUC on dev:

| band | AUC | mean score, undetermined states |
|---|---:|---:|
| well-below | **0.9976** | **0.2106** |
| near-threshold | 0.9345 | 0.1131 |
| above | 0.9822 | 0.0499 |
| well-above | 0.9833 | 0.0593 |

The scorer orders states *almost perfectly* inside the band it fails on. What
differs is where the score **levels** sit: undetermined states score about
twice as high in `well-below` as in `near-threshold`. One global threshold is a
single horizontal line across four vertically shifted distributions, so it
cuts each band at a different quantile.

> **Good ranking within every subgroup does not give a threshold that is safe
> within every subgroup. Conditional validity needs conditional
> *calibration*, not conditional ranking.**

This is the **third independent result** in this repository saying AUC cannot
see what this method does. The first: the excluded fitted scorer beat the
primary on coverage 97.7% to 74.8% at AUC 0.9644 against 0.9631. The second:
`sharpen` leaves AUC identical. The third is above.

### C3 missed, and it missed because the experiment was too small

C3 predicted some band would exceed α while the pooled rate stayed under it.
On dev, `hides_a_subgroup` was **False** at every tolerance. On the powered
benchmark it is **True**, with the worst band at 45.7% against a 20% budget.

**The underpowered experiment said there was no hidden subgroup. There was.**

### What round three actually established

That it could not answer its question. Both sides were too small, and
`src/abstain/power.py` says by how much:

- **Calibration.** Dev's 60% fold is 47 cases over four bands, ~11 each. A
  Clopper–Pearson bound at zero failures in 11 trials is still **23.8%**, so
  no tolerance at or below 20% is reachable in principle — and all three
  pre-registered tolerances were. The grouped rule was infeasible in 100% of
  trials, which is arithmetic rather than a finding.
- **Evaluation.** The deployment fold is ~32 cases, ~8 per band. A rate on 8
  cases moves in steps of **12.5 points**: 0/8 and 1/8 are 0% and 12.5%, and
  10% lies between them. Round three asked whether a band exceeded 10% on 8
  cases.

So D1 was not false. It was untestable, and reporting it false would have been
reporting noise.

### The requirement, computed rather than guessed

Closed form and exact binomial, no simulation, readable before collecting data:

| α | calibration cases/band | deployment cases/band | benchmark needed |
|---:|---:|---:|---:|
| 0.20 | 14 | 22 | 275 |
| 0.15 | 19 | 40 | 500 |
| 0.10 | **29** | **89** | **1,113** |

A failing test found a design defect along the way. The assertion was that the
total needed would come in under `calibration_total + deployment_total`, since
two folds drawn from one pool cost less than their sum. At α = 0.15 it is 500
against 295. **The 60/40 calibration share is tuned for pooled validation, and
group conditioning inflates the deployment requirement far harder** — a
per-band rate has to be resolvable in every band. The wrong share costs 1.7×
the cases.

---

## Round four — the benchmark the question needs

The household space is finite, and that turned out to be the binding
constraint. Ten incomes × 4 dependent counts × 4 ages × 4 states is **640
households**, so the original 160-case benchmark was a sample of a quarter of
one grid, and 640 is still 1.7× short at α = 0.10.

Refining income to every 3,000 from 0 to 60,000 gives 21 values and **1,344
households, all of which are built.** It is the *complete enumeration* of the
space, not a sample of it: the only randomness left is the dev/holdout split
and the per-trial draws. Every original income value is a multiple of 3,000,
so the coarse benchmark is a **subset** of this space — the two are the same
population at different resolutions, which is what makes this a replication
rather than a change of subject.

| | |
|---|---|
| Cases | 1,344, complete enumeration |
| Split | 672 / 672, seed 20261008, stratified by income band |
| Oracle | `policyengine-us==2.33.0`, recorded in the data |
| Trials | 400 per condition |
| Calibration share | **0.30**, from the power requirement, not inherited |
| Powered at | α = 0.20, 0.15 · α = 0.10 is **1.32× short** and labelled exploratory |

### E1 — the headline claim replicates

`fine_dev`, 672 cases, 400 trials, pooled rule:

| α | feasible | violations (feasible) | coverage | questions/case |
|---:|---:|---:|---:|---:|
| 0.20 | 400 | **1.5%** | 76.0% | 2.06 |
| 0.15 | 400 | **0.0%** | 78.4% | 2.15 |
| 0.10 *(exploratory)* | 400 | **0.0%** | 77.2% | 2.27 |

**E1 held.** The original holdout was 81 cases; this is 672 at 400 trials on a
freshly split, eight-times-larger benchmark, and the guarantee holds at every
tolerance. **E2 held** — coverage 76–78% against a predicted 60–85%, and
slightly above the coarse holdout's 75.3%, consistent with this benchmark's
heavier `well-above` share.

Note what else changed: α = 0.10 is now **feasible in 100% of trials** where
on the coarse benchmark α = 0.05 was infeasible in all of them. The binding
constraint was always sample size, exactly as `power.py` says.

### E3 and E8 — the concentration is real and it is the same band

`fine_dev`, pooled rule, 400 trials, deployments pooled across trials:

| α | pooled rate | worst band | its rate | concentration | hides a subgroup |
|---:|---:|---|---:|---:|:--:|
| 0.20 | 11.1% | `well-below` | **45.7%** | **4.12×** | **yes** |
| 0.15 | 7.5% | `well-below` | **29.0%** | 3.85× | **yes** |
| 0.10 | 4.5% | `well-below` | 13.7% | 3.04× | **yes** |

**E3 and E8 both held.** The same band concentrates, so the mechanism
diagnosed on the coarse grid transfers. And the magnitudes are no longer
ambiguous: 26,752 deployed `well-below` cases rather than 8 per trial.

The fairness reading is the one that matters. `well-below` is households under
$6,000 of employment income — the applicants most likely to be eligible and
least able to absorb a wrong decision. **At a 20% budget they receive a
decision built on a guess 45.7% of the time, while the headline number reads
11.1%.**

### The measurement defect that inverted this comparison

Before the scheme comparison could be read, a second bug had to come out, and
it is the same species as the first: a metric measuring the wrong thing in the
direction that flattered the method.

`evaluate_by_group` used one parameter for two jobs — which threshold a case
is judged against, and how results are broken down. Under `scheme="pooled"`
there is a single calibration group, so bucketing results by it gave **one
bucket**: `worst_group_rate` returned the pooled rate and `max_concentration`
was 1.00 by definition.

The pre-fix table reported, at α = 0.20, a worst group of 11.1% and a
concentration of 1.00 for the pooled rule, against 12.9% and 1.80 for the
grouped one. **That reads as group conditioning making things worse on exactly
the axis it was built to improve**, and it was an artefact of scoring the two
schemes against different partitions. The real pooled figure, measured on
bands, is 45.7%.

The partitions are now separate arguments; the measurement partition is the
bands regardless of how calibration was grouped; and the pre-fix run is kept
in `evidence/round4-dev-prefix-run.txt`. A comparison between schemes is only
a comparison if every scheme is scored against the same partition.
