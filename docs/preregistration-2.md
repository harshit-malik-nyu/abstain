# Pre-registration, round two

Written before any of the code the three experiments below need. The git
history shows this commit precedes `src/abstain/robustness.py`,
`src/abstain/conditional.py`, and the `bound=` parameter on
`calibrate_on_trajectories`.

---

## Why a second one

The first pre-registration covered the primary claim: an operator names α and
gets it. That claim held on holdout. It leaves three questions a reader is
entitled to ask and this repository has not answered:

1. **Why not just pick a threshold?** The method's extra machinery is a
   Clopper–Pearson upper bound in place of the empirical rate. Nowhere is the
   empirical rate actually run, so the conservatism is unjustified — it is
   asserted to be necessary rather than shown to be.

2. **Your scorer is a toy.** `docs/against.md` already leads with this. The
   theory says the bound holds for *any* fixed score, which would make the
   scorer's quality a coverage question and not a safety question. That is a
   strong claim and it has never been tested against a score that is actually
   bad.

3. **Marginal coverage hides subgroup failure.** Every number reported so far
   is pooled. A 5% budget spent entirely on the hardest 20% of cases is a 25%
   failure rate for those applicants, and the pooled figure would not show it.

Each is answerable with the data already in hand. Each is written down below
before it is run.

## Where these run, and what that costs

**On dev.** The holdout was opened once, for the primary result, and that is
the only thing it can carry at full strength. Reusing it for three secondary
analyses would spend its discipline on questions it was not reserved for, and
every additional look inflates the chance that something passes by luck.

So these are dev experiments and are labelled as such. One consequence worth
stating plainly: **a dev result is weaker evidence than a holdout result**, and
anything below that happens to support the method should be read at that
discount. The experiments are pre-registered anyway, because the value of
writing predictions down first does not come from which set they are checked
against — it comes from not being able to choose the interpretation afterwards.

**One confirmatory holdout look is reserved**, for prediction B1 only — the
claim that the bound survives a useless score. That is the one result here
that is load-bearing for the theory rather than descriptive, and it is the one
worth a second opening. This is holdout opening **#2**. With two openings and
the predictions tested on the second, the reported significance is
Holm–Bonferroni corrected over the holdout-tested predictions, and the count
of openings is stated in the README so a reader can discount accordingly.

Nothing else touches holdout.

---

## Experiment A — the plug-in baseline

### What is being compared

Identical pipeline, one line different. Both choose the smallest threshold on
the pre-specified 101-point grid whose calibration unsafe rate is within α.
They differ in what "within α" means:

| | threshold accepted when |
|---|---|
| **conformal** (the method) | Clopper–Pearson upper bound at δ ≤ α |
| **plug-in** (the baseline) | empirical rate ≤ α |

The plug-in is not a straw man. It is what a competent engineer writes when
asked to hold an error budget, and it is correct *in expectation* — which is
exactly the property that makes it fail, because an operator who asked for 5%
and gets 5% half the time has not been given a guarantee.

### Predictions

**A1.** At every α tested, the plug-in's violation rate will exceed δ = 0.05.
This is the baseline failing, and it is the claim that justifies the method
existing.

**A2.** The plug-in's violation rate will **rise as the calibration set
shrinks**. Small-sample optimism is the mechanism, so the effect should be
monotone in calibration size over 20, 30, 40, 50 cases.

**A3.** The conformal rule's violation rate will stay **at or below δ at every
calibration size**, including the smallest. Where it cannot, it will report
infeasible rather than violating.

**A4.** The plug-in will have **higher coverage** than conformal at matched α.
This matters: if the plug-in were worse on both axes the comparison would be
meaningless and something in the implementation would be wrong. The method is
buying safety with coverage and the price should be visible.

### What would falsify A

- **A1 fails** — the plug-in holds δ too. Then the Clopper–Pearson bound is
  unnecessary at this sample size and the method is over-engineered. That is a
  reportable negative result about the method, not about the baseline.
- **A3 fails** — the conformal rule violates where the plug-in does. Then the
  primary result was a property of the draw.
- **A4 fails** — conformal has coverage at or above plug-in. Then the two are
  not making the trade I claim they are and the comparison needs rebuilding
  before it means anything.

---

## Experiment B — does the bound survive a bad score?

### The corruptions

Each is a fixed transformation of `handcrafted_scorer`, chosen before running
and applied **identically in calibration and deployment**, so exchangeability
is preserved. That is the condition the conformal argument needs; these
experiments vary score *quality*, not the assumption.

| name | transform | what it imitates |
|---|---|---|
| `identity` | s | control |
| `coarse` | round s to nearest 0.1 | the clumping a language model's self-reported confidence shows — values pile on 0.9, 0.95, 1.0 |
| `sharpen` | s<sup>1/4</sup> | overconfidence. **Strictly monotone**, so the ordering, and therefore AUC, is unchanged |
| `noisy(σ)` | s + N(0, σ), clipped | progressive loss of ordering, σ ∈ {0.1, 0.25, 0.5} |
| `constant` | 0.5 | a score carrying no information at all |
| `inverted` | 1 − s | adversarially anti-correlated: the least safe states score highest |

`inverted` is the important one. It is not a plausible scorer; it is the worst
case the theory claims to cover. If the bound holds there it holds anywhere.

### Predictions

**B1.** The violation rate will be **at or below δ for every corruption**,
including `constant` and `inverted`. This is the theory's actual claim and the
only prediction here checked on holdout.

**B2.** `sharpen` will leave coverage **within 5 percentage points** of
`identity`. The rule's stopping condition compares the score to a threshold
and so uses only its order — a strictly monotone transform should pass through
it. This is a real risk rather than a safe bet: the greedy question-selection
rule `_default_choice` picks the field with the largest score *difference*, and
differences are not monotone-invariant. If B2 fails, the architecture is
value-sensitive somewhere it was described as order-sensitive, and finding that
is worth more than the prediction being right.

**B3.** Coverage will be **monotone non-increasing in σ** across
`noisy(0.1) → noisy(0.25) → noisy(0.5)`. Worse ordering, less resolved.

**B4.** `constant` and `inverted` will fail **by infeasibility, not by
violation** — the rule will report that no threshold achieves the tolerance,
in the majority of trials, rather than deploying an unsafe one. A method whose
failure mode is refusing to certify itself is usable; one whose failure mode is
silently exceeding the budget is not.

### What would falsify B

- **B1 fails for any corruption.** Then the guarantee depends on the score
  being reasonable, the theory section overstates what is proved, and
  `docs/theory.md` has to be rewritten. This is the outcome that would matter
  most.
- **B4 fails** — `constant` or `inverted` reports feasible and then violates.
  Same consequence as B1 failing and worse, because the rule would be issuing
  a certificate it cannot honour.

### What would not falsify B

- **B2 failing.** It is a prediction about the architecture, not the
  guarantee. A value-sensitive question-selector is a design observation.
- **B3 being non-monotone at one step.** Three σ values on 79 cases is a
  small sample and a single inversion is noise. A reversal across the full
  range would not be.

---

## Experiment C — is the budget spent uniformly?

### What is measured

Every result so far is marginal: one unsafe rate pooled over all cases. The
conformal guarantee is marginal too — it says nothing about any subgroup, and
that is a known and well-documented limitation of split conformal methods
rather than something specific to this one.

So: break the deployed unsafe rate and the coverage down by the stratum used
for the split — income relative to the eligibility boundary, the four bands in
`scripts/split.py`.

### Predictions

**C1.** Violations will be **concentrated in `near-threshold`** — that
stratum's share of unsafe commitments will exceed its share of the deployed
cases. Near the boundary is where the unknown fields actually move the verdict,
so it is where committing early is wrong.

**C2.** Coverage will be **lowest in `near-threshold`** and highest in the two
extreme bands.

**C3.** At α = 0.10, at least one stratum will have an unsafe rate **above
0.10** while the pooled rate is below it. If so, the pooled guarantee hides a
subgroup it does not cover, and that has to be said in the README rather than
in a footnote.

### What would falsify C

Nothing. **C is descriptive, and both outcomes are publishable.** If the
budget is concentrated, the method has a limitation worth naming loudly. If it
is spread evenly, marginal and conditional coverage approximately coincide on
this benchmark, which is a reassuring measurement and does not generalise to
benchmarks with stronger subgroup structure.

Stating that in advance is the point: a descriptive experiment where either
result is interesting is one I cannot spin, and writing down that I cannot
spin it is what keeps the write-up honest.

---

## Analysis plan

| | |
|---|---|
| **Set** | `evidence/dev.json`, 79 cases, for A, B and C |
| **Holdout** | B1 only, one run, opening #2 |
| **Trials** | 150 per condition, matching the primary result |
| **Seeds** | A: 11 · B: 13 · C: 17 — fixed here, not chosen after |
| **α** | 0.20, 0.15, 0.10 (0.05 is infeasible at this size and known to be) |
| **Multiplicity** | Holm–Bonferroni over holdout-tested predictions |

No tuning after running. A prediction that misses is reported as a miss, with
a test that pins the miss so it cannot quietly disappear from a later edit —
the same mechanism `tests/test_preregistration.py` already uses for P2.
