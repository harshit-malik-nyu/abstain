# A selection rule that bounds how often an agent answers blind

An agent conducting a benefits intake can ask for a field or commit to a
verdict. Committing while the case is still undecidable is the failure that
matters, because downstream it becomes a filed claim built on a guess. A
companion benchmark measured a frontier model doing exactly that on **62.5%**
of undecidable cases.

This is a rule where the operator names a tolerance and gets it:

> give me an unsafe rate at or below α, and resolve as much as possible
> subject to that

It holds. And the most useful thing in this repository is what measuring it
carefully turned up — three bugs in the rule's own favour, two predictions I
got backwards, and one result that changes what the method is for.

---

## The finding that matters most

The guarantee is **marginal**. It bounds the error rate over the population and
says nothing about any subgroup of it. That is the standard caveat on split
conformal methods, usually written in a limitations section and left there.

Measured, on 672 cases and 400 trials at α = 0.20:

| | |
|---|---:|
| Trials where the rule honoured its budget **overall** | **98.5%** |
| Trials where it broke that budget **for some income band** | **98.2%** |

The band is always the same one. `well-below` — households under $6,000 of
employment income — runs at **45.7% unsafe** against a 20% budget, absorbing
**4.1×** its proportional share, while the headline number reads 11.1%.

Those are the applicants most likely to be eligible and least able to absorb a
wrong decision. **At a stated 20% tolerance they receive a decision built on a
guess nearly half the time, and the pooled certificate says the rule is
working.**

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

Same pipeline, same grid, α = 0.10, 150 trials:

| Calibration cases | Conformal | Plug-in |
|---:|---:|---:|
| 40 | **3.3%** violations | **16.7%** |
| 50 | **0.7%** violations | **20.7%** |

The plug-in never reports infeasible. It always has a threshold to offer, and
the threshold is not safe.

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

## Three bugs, all in the method's favour

Worth its own section, because the pattern is the point: **every defect found
by scrutiny made the method look better than it was**, and none was found by
the experiment that was supposed to validate it.

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

**That is now the third independent result here saying AUC cannot see what this
method does.** The second: the `sharpen` corruption leaves AUC identical to the
floating-point bit. The third: every band above 0.93 while one absorbs 4.1× its
share of the budget.

---

## What is guaranteed, and on what basis

Three claims resting on different things. [`docs/theory.md`](docs/theory.md)
separates them.

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
match. `split.py` later grew options so the second benchmark could reuse its
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

## Status

Built, validated, replicated, and reported including every prediction that
missed, every judgement that was wrong, and every bug that flattered it.

## License

MIT. Derived from the `underdetermined` benchmark in the same account.
