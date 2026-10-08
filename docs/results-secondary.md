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

### E4–E7 — what group conditioning costs, once measured right

`fine_dev`, 400 trials, paired on identical draws, measured on bands under
every scheme.

| α = 0.20 | feasible | violations (pooled) | violations (per band) | worst band | coverage | questions |
|---|---:|---:|---:|---:|---:|---:|
| pooled | 400 | 1.5% | **98.2%** | **45.6%** | 76.0% | 2.06 |
| **by-band** | 389 | 0.0% | **3.3%** | **12.9%** | **81.0%** | **1.89** |
| separate-well-below *(post-hoc)* | 400 | 0.2% | 62.3% | 24.1% | 79.0% | 1.92 |

| α = 0.15 | feasible | violations (per band) | worst band | coverage |
|---|---:|---:|---:|---:|
| pooled | 400 | 88.5% | 28.8% | 78.4% |
| **by-band** | 264 | **5.3%** | **8.6%** | **80.3%** |
| separate-well-below *(post-hoc)* | 393 | 44.5% | 13.4% | 80.7% |

**E4 held** — feasible in 389/400 trials at α = 0.20. **E5 held
emphatically.** **E7 held**, and sharpened its own warning: the two-group
scheme sits between, but far nearer the pooled rule on the subgroup measure
(62.3% against 3.3%). **Separating the band you know fails leaves the bands
you did not check sharing a threshold, and one of them then exceeds budget.**
That is the argument for the full version over a scheme fitted to this
benchmark, and the pre-registration made it before it was measured.

At α = 0.10 `by-band` is feasible in **7 of 400 trials**. That is not a
finding; it is the power requirement, which said 890 cases were needed and 672
were available. The 7-trial figures are not interpretable and are reported as
such.

### E6 missed, and the miss is the most useful thing in the round

I pre-registered that group conditioning would **cost coverage** — four
conservative thresholds abstain more than one. It is safer per band, resolves
**more**, and asks **fewer** questions.

Per band at α = 0.20:

| band | unsafe (pooled → by-band) | coverage | abstains | questions |
|---|---|---|---|---|
| **well-below** | **45.7% → 5.6%** | **54.3% → 92.4%** | 0.0% → 2.0% | 1.67 → 2.15 |
| near-threshold | 5.2% → 4.1% | 75.4% → 75.9% | 19.4% → 20.0% | 2.28 → 2.29 |
| above | 5.6% → 6.2% | 68.3% → 70.8% | 26.1% → 22.9% | 2.41 → 2.26 |
| well-above | 5.4% → **10.8%** | 88.4% → 85.8% | 6.2% → 3.4% | 1.85 → 1.31 |

Three things fall out of that table.

**The pooled rule never abstains on the band it fails.** `well-below`'s
abstention rate is **0.0%**, and 54.3% coverage plus 45.7% unsafe is 100%: it
commits on every case. That band's undecidable states carry the highest score
levels of any band, so they clear a globally-set threshold immediately — and
the abstention mechanism, the whole point of the method, is inactive precisely
where it is most needed.

**The mechanism is question allocation, not risk allocation.** The global
threshold asks **1.67** questions of the band running at 45.7% unsafe and
**1.85** of a band at 5.4%. It is not under-asking uniformly; it is
under-asking in exactly the wrong direction. Conditioning moves half a
question from `well-above` to `well-below` and the **total falls** — 1.89
against 2.06.

> A single global threshold mis-allocates questions. It under-asks of the
> applicants whose answers are least determined, and over-asks of everyone
> else.

**Which is why safety and coverage move together.** `well-below`'s abstention
rises only from 0.0% to 2.0%, so the gain is not from abstaining. It is one
more question, after which the case is decidable and a blind commitment
becomes an informed resolution. An 8× reduction in unsafe commitments and 38
points of coverage, for half a question.

The cost lands on `well-above`: 5.4% → 10.8%, still well inside a 20% budget.
It was over-protected by a threshold set for another band and now spends its
own. At α = 0.15 the least-served band is marginally worse for the same reason
(65.4% → 63.2%).

---

## Round five — the assumption, priced

[Pre-registered here.](preregistration-5.md) Calibrate on the natural band
mix; deploy on a mix where `well-below`'s share is forced upward. 300 trials
per point, `fine_dev`.

| `well-below` share | pooled | **by-band** | bound the rule reported | distinct cases |
|---:|---:|---:|---:|---:|
| **α = 0.20** | | | | |
| 14.3% *(natural)* | 0.7% | 0.0% | 0.175 | 63.3% |
| 25% | 17.0% | 0.0% | 0.175 | 61.9% |
| 40% | 65.3% | 0.0% | 0.175 | 56.7% |
| 60% | 92.3% | 0.0% | 0.175 | 46.0% |
| 80% | 95.3% | 0.0% | 0.175 | 32.1% |
| **100%** | **98.0%** | **0.7%** | **0.175** | 14.3% |
| **α = 0.15** | | | | |
| 14.3% | 0.0% | 0.0% | 0.127 | 63.3% |
| 25% | 13.0% | 0.0% | 0.127 | 61.9% |
| 40% | 27.0% | 0.0% | 0.127 | 56.7% |
| 60% | 79.3% | 0.5% | 0.127 | 46.0% |
| 80% | 89.3% | 1.5% | 0.127 | 32.1% |
| **100%** | **91.3%** | **2.4%** | **0.127** | 14.3% |

**All five predictions held.**

**F1** — the control sits at 0.7% and 0.0%, matching the ordinary validation
path. **F2** — monotone at both tolerances. **F3** — 98.0% at full shift,
against a predicted 80%.

**F4, the prediction worth the round, held.** Group conditioning stays inside
δ at every shift level and is **140× better at full shift**. Not a lucky
robustness property but the construction: re-weighting groups calibrated
separately changes *which* thresholds get used, not *what any threshold is.*
The guarantee was never a statement about the mixture.

> So the fairness finding and the robustness finding are the same finding. The
> subgroup that absorbs the error budget is exactly the subgroup whose
> over-representation breaks the pooled rule, and one threshold per group
> fixes both at once.

**F5 held, and it is the most damning column in this document.** The reported
bound is **0.175 at every shift level** — identical, while the deployed
violation rate climbs from 0.7% to 98.0%. The bound is computed on calibration
data and calibration data is unshifted, so the certificate the method issues is
the same whether it is honouring its budget or breaking it 98% of the time.
**An operator watching the reported bound would see nothing wrong.**

### What round five does not show

That the method is safe under shift. It is not, and the table is how unsafe.

And group conditioning's invariance is narrow. It covers a shift in the
**proportions** of groups that were calibrated separately. A shift *within* a
band, a band calibration never saw, or a change in the relationship between
score and determinability breaks it exactly as they break the pooled rule.
`group.threshold_for` refuses to serve a group calibration never saw rather
than borrowing another group's threshold, which is honest behaviour and not a
solution. Weighted conformal methods for covariate shift exist; none is
implemented here.

One limitation of the harness: forcing a 14.3% band to 80% of the fold
requires resampling with replacement, so the high-shift rows rest on fewer
distinct cases — the last column, down to 14.3% at full shift. Reported per
row rather than left to the reader.

---

## The pattern across all four rounds

Three bugs were found by scrutiny, and **every one made the method look better
than it was**:

| bug | what it hid | how it survived |
|---|---|---|
| refusal threshold of `1.0` | the rule committing blind after declining to certify itself | the one scorer ever used tops out at 0.9718; a passing test asserted the wrong value |
| one parameter for calibration and measurement partitions | the pooled rule's real worst-band rate, 45.7% reported as 11.1% | the pooled scheme has one group, so the breakdown was trivially flat |
| violation rate pooled over declined trials | the difference between "held", "failed" and "never certified" | every condition was feasible until corruptions made them not |

None was found by the experiment meant to validate the method. All three were
found by experiments built to attack it, and two were found only because the
corruption study ran scorers the primary experiment never would have.

Five predictions missed across the four rounds: **A2** (monotonicity in
calibration size), **C1** and **C2** (the wrong band, twice), **C3** (which
was right and unmeasurable at 79 cases), and **E6** (coverage cost, which was
a coverage gain). Each is recorded as a miss with a test pinning it.

---

## Round four, confirmatory — the fine holdout, opened once

672 cases this method was never developed against. Same code path, same seed,
same trial count, `fine_dev` swapped for `fine_holdout`.

**The run was interrupted partway through** by the session it was running in,
after the replication and concentration tables had printed. It was relaunched
rather than re-designed, and the claim that this is one draw rather than two
looks is checked rather than asserted:
[`scripts/verify_resumed_run.py`](../scripts/verify_resumed_run.py) requires
every numeric row the interrupted log printed to reappear character for
character in the completed one. **All 36 do.** The interrupted log was
committed before the relaunch so it could not be edited to match, and tests
assert both that ordering and that `run_round4.py` was unmodified between the
two.

### E1 and E2 — the guarantee

| α | feasible | violations | coverage | questions/case |
|---:|---:|---:|---:|---:|
| 0.20 | 400 | **0.0%** | 75.1% | 2.04 |
| 0.15 | 400 | **1.8%** | 77.1% | 2.17 |
| 0.10 *(exploratory)* | 400 | **0.0%** | 77.8% | 2.27 |

### E3 and E8 — the concentration is worse here than on dev

| α | pooled | worst band | its rate | concentration | hides a subgroup |
|---:|---:|---|---:|---:|:--:|
| 0.20 | 11.5% | `well-below` | **49.0%** | **4.24** | **yes** |
| 0.15 | 7.3% | `well-below` | 31.9% | **4.35** | **yes** |
| 0.10 | 4.1% | `well-below` | 13.9% | 3.44 | **yes** |

Against dev's 45.7% and 4.12 at α = 0.20. **A result that degrades from dev to
holdout is the usual signature of tuning; one that gets worse against the
method cannot be.**

### E4–E7 — the schemes

| α = 0.20 | feasible | violations (per band) | worst band | coverage | questions |
|---|---:|---:|---:|---:|---:|
| pooled | 400 | **99.8%** | **48.8%** | 75.1% | 2.04 |
| **by-band** | 370 | **3.5%** | **12.8%** | **78.0%** | **1.90** |
| separate-well-below *(post-hoc)* | 400 | 69.5% | 24.8% | 78.6% | 1.91 |

| α = 0.15 | feasible | violations (per band) | worst band | coverage |
|---|---:|---:|---:|---:|
| pooled | 400 | 82.5% | 31.7% | 77.1% |
| **by-band** | 163 | **5.5%** | **9.7%** | **78.5%** |
| separate-well-below *(post-hoc)* | 393 | 39.4% | 13.8% | 80.7% |

**E5 replicates, and so does E6's reversal** — conditioning is safer per band,
resolves more, and asks fewer questions, on data it was never developed
against.

**E7 replicates, and the post-hoc warning lands.** The two-group scheme sits
at 69.5% subgroup violations against the full scheme's 3.5%. A scheme fitted
to the group you watched fail does not protect the groups you did not check,
and that was written down before it was measured.

At α = 0.10 `by-band` is feasible in **12 of 400 trials**. Its figures are not
interpretable and are not interpreted — which is what
[`power.py`](../src/abstain/power.py) said before the run, having computed
that 890 cases were needed and 672 were available.

---

## The addendum — "just recalibrate"

Round five holds calibration at the natural mix throughout, which models the
*onset* of a shift and invites a one-line rebuttal: of course the pooled rule
fails, it was never allowed to recalibrate. If that holds, the recommendation
from this project collapses to *recalibrate when your population moves* —
easier, and already standard practice. [Pre-registered as G1–G3](preregistration-5.md#addendum--the-objection-round-five-invites)
before the code existed, then run.

Same sweep, calibration fold reweighted to the deployment mix. 300 trials,
α = 0.20.

| `well-below` share | violations, stale | violations, **recalibrated** | worst band | concentration | hides a subgroup |
|---:|---:|---:|---:|---:|:--:|
| 14.3% *(natural)* | 0.7% | 0.7% | **45.1%** | **4.03** | **yes** |
| 25% | 17.0% | 2.0% | 30.8% | 2.86 | **yes** |
| 40% | 65.3% | 2.3% | 22.1% | 2.02 | **yes** |
| 60% | 92.3% | 8.0% | 17.2% | 1.48 | no |
| 80% | 95.3% | 12.7% | 14.1% | 1.19 | no |
| 100% | 98.0% | 9.3% | 12.7% | 1.00 | no |

### G3 held, and it is the answer

At the mix an operator actually faces, a **freshly recalibrated** pooled rule
still runs the lowest-income band at **45.1%** against a 20% budget, at
**4.03×** its share. The stale rule's figures are 45.7% and 4.12×. The
difference is under a point.

> Recalibration fixes the **marginal** failure and leaves the **conditional**
> one exactly where it was. The fix is *calibrate per group*, not
> *recalibrate often.*

That is not an argument against recalibrating. It is an argument that
recalibrating answers a different question, and that the cheaper
recommendation is not available.

The concentration does fall at the right of the table, for a reason that is
not reassuring: once one band is 80% of the cases there is barely a disparity
left to have, and at 100% the figure is 1.00 by definition.

### G1 missed

The prediction was that recalibration would return violations to at or below
δ = 0.05 **at every** shift level. It does at the first three and not the last
three — 8.0%, 12.7%, 9.3%.

The likely cause is the harness rather than the method. Forcing a band that
holds 96 distinct cases up to 80% of a fold requires resampling with
replacement, so the calibration fold at those points is built from few distinct
cases and its exchangeability with deployment is weakened by the resampling
itself rather than by the shift. **That is an explanation and not an excuse**,
and a test pins the miss so that a future run meeting δ everywhere forces the
write-up to stop calling it one.

### G2 held, and shrank the claim it was testing

Group conditioning's coverage advantage falls from **+38.4 points** against a
stale threshold to a steady **+3.7 to +4.0** against a fresh one. Most of the
larger number was staleness, and reporting the smaller one is more useful than
keeping the headline.

Two sanity checks sit inside that result. At a 100% share the two schemes come
out **identical** — 87.3% each — because one band is one group, which is what
a correct implementation must do. And at an 80% share group conditioning is
infeasible in **all 300 trials**; a mean coverage over no feasible trial is
0.0, and printing that as zero coverage would read as *resolved nothing* when
it means *never certified*. Opposite implications, so it reports `n/a`.

---

## Addenda two and three — how much of this is the scorer?

The subgroup finding rested on one hand-built scorer, and the mechanism
diagnosis blames one hand-written feature. I claimed the concentration was a
property of **using one threshold** rather than of that feature, and
[pre-registered two tests](preregistration-5.md) of it. 200 trials,
`fine_dev`, α = 0.20, each learned scorer refit per trial on a fold disjoint
from calibration and deployment.

| scorer | AUC | pooled unsafe | coverage | worst band | its rate | concentration | hides a subgroup |
|---|---:|---:|---:|---|---:|---:|:--:|
| handcrafted | **0.9555** | 11.1% | 76.0% | `well-below` | **45.9%** | **4.13** | **yes** |
| fitted, same features | 0.9252 | 11.8% | 88.1% | `well-below` | 39.2% | **3.31** | **yes** |
| **fitted, no distance feature** | **0.8888** | **7.3%** | **92.7%** | `well-below` | **12.5%** | **1.72** | **no** |

### The strong claim is refuted

**J1 failed.** Removing the one feature the mechanism blames cuts the
concentration from 4.13 to **1.72** and brings every band inside budget. The
claim that the concentration is a property of single-threshold calibration
*rather than* of the score does not survive.

What does survive:

> The concentration is driven **primarily by a score feature that is
> systematically wrong for one group**, and a single threshold cannot absorb
> that. It is not an artifact of the hand-built functional form — learning the
> weights over the same features still leaves 3.31. Remove the feature and the
> disparity shrinks 2.4×; it does **not** vanish, and the same band is still
> worst at 1.72× its share.

Had the prediction not been written down first, "a single threshold
concentrates harm" is exactly the kind of claim that survives on two
confirming arms and never meets the third.

The practical reading is more useful than the claim it replaces: **a feature
that is directionally wrong for a group is the first thing to look for**, and
removing it beat every other intervention measured here while improving pooled
safety and coverage at the same time.

### Four predictions, three missed

**J2 held** — the same band is worst under all three scorers.

**J1, J3 and J4 all missed, in the same direction.** J3 predicted the crippled
scorer's coverage would fall below 60%; it is **92.7%**, the highest of the
three. J4 predicted its AUC below 0.80; it is 0.8888. I badly underestimated
how much signal the known-field pattern alone carries.

**H3 missed** in the other direction: I predicted the fitted scorer's pooled
unsafe rate would be at or below the handcrafted one's, and it is higher at
both tolerances — it commits far more often, so it commits wrongly more often
in absolute terms while resolving twelve points more.

### H4 held, and the arm that tested it had to be rewritten first

The first version of this experiment passed `handcrafted_scorer` to every row
of the H4 table, because `validate_groups` had no way to refit. It printed a
table that looked like an answer to "does conditioning fix the *learned*
scorer" and was a duplicate of round four's scheme comparison. Nothing failed
and nothing warned — **a missing capability that quietly changes which
question is being answered is worse than one that raises an error.**

With refit added:

| scorer, α = 0.20 | violations per band | worst band | coverage |
|---|---:|---:|---:|
| handcrafted, one threshold | 99.0% | 45.8% | 76.0% |
| handcrafted, **per band** | **2.6%** | **13.0%** | **80.3%** |
| fitted, one threshold | 86.5% | 38.9% | 88.1% |
| fitted, **per band** | **7.0%** | **12.1%** | **92.0%** |

Pareto again, on a scorer the fix was never designed around.

### The fourth AUC result, and the only one that points backwards

Read the first two columns of the scorer table together. **The scorer with the
worst AUC has the lowest pooled unsafe rate and the highest coverage.** 0.8888
against 0.9555, better on both axes the method actually optimises.

The earlier three showed AUC failing to *discriminate*. This one shows it
ranking three scorers in exactly the wrong order. A ranking metric scores a
scorer on pairs it will never be asked about; a threshold-local rule is judged
on one cut.
