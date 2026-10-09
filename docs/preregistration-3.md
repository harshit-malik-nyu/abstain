# Pre-registration, round three — the fix for what C found

Written before `group_conditional` exists in `src/abstain/`. The git history
shows this commit precedes it.

---

## What C found, and why it needs an answer rather than a caveat

Experiment C predicted the error budget would concentrate on `near-threshold`
cases. It missed in three ways at once, and the shape of the miss is the
reason this document exists.

At α = 0.20, pooled over 150 trials on dev:

| band | deployed | unsafe | rate | concentration |
|---|---:|---:|---:|---:|
| well-below | 1,056 | 203 | **19.2%** | **3.44×** |
| near-threshold | 1,627 | 0 | 0.0% | 0.00× |
| above | 1,158 | 65 | 5.6% | 1.01× |
| well-above | 959 | 0 | 0.0% | 0.00× |

Pooled: **5.6%**. One band at **19.2%**. The predicted band at zero.

The mechanism is not bad ranking. Per-band AUC on dev:

| band | AUC | mean score, undetermined states |
|---|---:|---:|
| well-below | **0.9976** | **0.2106** |
| near-threshold | 0.9345 | 0.1131 |
| above | 0.9822 | 0.0499 |
| well-above | 0.9833 | 0.0593 |

The scorer orders states *almost perfectly* inside the band it fails on. What
differs between bands is where the score levels sit: undetermined states in
`well-below` score about twice as high as undetermined states in
`near-threshold`. A single global threshold is one horizontal line across four
vertically shifted distributions, so it cuts each band at a different quantile.

> **Good ranking within every subgroup does not give you a threshold that is
> safe within every subgroup. Conditional validity needs conditional
> *calibration*, not conditional ranking.**

Two consequences worth separating:

**It is a fairness problem, not only a statistical one.** `well-below` is the
lowest-income band — households under $6,000 of employment income. They are
the applicants most likely to be eligible and least able to absorb a wrong
decision, and they are the ones the rule commits blind on. A pooled 5.6% that
is 19.2% for them is the kind of number that should not appear only in a
breakdown.

**It is the third independent result in this repository saying AUC cannot see
what this method does.** The first: the excluded fitted scorer beat the
primary on coverage, 97.7% against 74.8%, with AUCs of 0.9644 and 0.9631.
The second: `sharpen` leaves AUC identical to the floating-point bit. The
third is above — every band over 0.93, and a 3.4× disproportion. A ranking
metric is being used to choose between threshold-local decision rules, and it
is blind to all three.

## What is being added

**Group-conditional calibration.** One threshold per band instead of one
threshold overall: the calibration cases are partitioned by band, each
partition gets its own Clopper–Pearson search, and at deployment a case is
judged against its own band's threshold.

This is **not novel**, and saying so is part of the point. It is Mondrian
conformal prediction — Vovk and colleagues, mid-2000s — and group-conditional
coverage has an established literature in conformal prediction since. The
contribution here is not the construction. It is measuring what the
construction costs on a benchmark where the failure it fixes is real, and
reporting the sample size at which it becomes affordable.

## The cost, stated before measuring it

Splitting calibration four ways divides n by four, and the Clopper–Pearson
floor is what binds. With zero observed failures in n calibration cases the
bound is 1 − δ<sup>1/n</sup>, so the smallest tolerance reachable at all is

| cases per band | tightest reachable α at δ = 0.05 |
|---:|---:|
| 7 | 34.8% |
| 10 | 25.9% |
| 20 | 13.9% |
| 29 | **9.9%** |

*Corrected after the fact, and the table left as written because a
pre-registration is not edited: the last cell is `reachable_alpha(29)`, which
is **9.81%** and rounds to **9.8%**. The round's argument uses 29 as the
smallest group size that can certify a 10% tolerance, which is right —
`minimum_calibration_size(0.10)` returns 29 — and the misprint is in the floor
beside it.*

Dev holds 79 cases; a 60% calibration fold is 47, which is about 11 per band.
So the prediction is not subtle.

## Predictions

**D1.** Group-conditional calibration will **remove the concentration**: at
every α where it is feasible, no band's unsafe rate will exceed α, and the
maximum concentration ratio across bands will fall below 2.0 from 3.44.

**D2.** It will be **infeasible at α = 0.10 in the large majority of trials**
(≥ 80%) at dev's calibration size, because 11 cases per band cannot reach a
10% tolerance at δ = 0.05 even with zero observed failures.

**D3.** Where feasible, **coverage will be lower** than the pooled rule's —
four conservative thresholds abstain more than one. The gap is the price of
conditional validity and the number worth having.

**D4.** The violation rate on feasible trials will stay **at or below δ** for
both rules. The pooled rule is not *invalid*; it is valid marginally and
misleading conditionally, and D4 is the check that I have not confused the two.

**D5.** A **partial pooling** variant — group-conditional on the one band that
fails, pooled across the other three — will be feasible at α = 0.10 in the
majority of trials *and* bring `well-below` under α. Two groups instead of
four costs less calibration data, and the failure is concentrated in one band
rather than spread across all of them.

D5 is the prediction I would most like to be right and the one I am least
confident in, because choosing which band to separate *using C's result* is a
data-dependent choice and the honest version of it has to be reported as such
(see below).

## The thing that would make D5 dishonest if unstated

D5 separates `well-below` because experiment C showed `well-below` failing.
That is selection on the outcome. A threshold scheme chosen after seeing which
group fails is fitted to this benchmark, and its apparent success does not
transfer to a deployment whose failing group is different.

So D5 is reported as **what it is: a post-hoc scheme, measured on dev, with no
claim of generalisation.** The defensible version for a practitioner is D1's
full group-conditional rule, which needs no knowledge of which band will fail
and is why D1 and not D5 is the primary prediction here.

## What would falsify this round

- **D1 fails** — per-band thresholds do not fix the concentration. Then the
  diagnosis in the first section is wrong: the problem would not be shifted
  score levels, and the mechanism needs rebuilding before the finding stands.
- **D4 fails for the pooled rule** on feasible trials. Then the primary result
  was luck and everything above is moot.

## What would not falsify it

- **D2 or D3 being wrong in either direction.** Both are cost predictions at
  one sample size. Cheaper than predicted is good news, not a refutation.
- **D5 failing.** It is a post-hoc variant and is labelled one.

## Analysis plan

| | |
|---|---|
| **Set** | `evidence/dev.json`, 79 cases |
| **Holdout** | not touched by this round |
| **Trials** | 150 per condition |
| **α** | 0.20, 0.15, 0.10 |
| **Seed** | 23 — fixed here |
| **Rules compared** | pooled · group-conditional (4 bands) · partial (2 groups) |

Also computed and reported: the **minimum calibration cases per band** needed
to reach each α at δ = 0.05, from the Clopper–Pearson floor directly. That is
the actionable output of this round — an operator who wants group-conditional
safety at a stated tolerance can read off how much calibration data to
collect, and it is a closed-form number rather than an experimental one.
