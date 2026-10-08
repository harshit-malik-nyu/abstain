# The case against this result

The strongest argument that it should not change how anyone builds an agent.

---

## 1. There is no model in it

The rule is evaluated against an oracle-backed simulation of an intake
interview. No language model was run. The score is a hand-written function of
four fields, and the "agent" is a loop.

So this demonstrates that **a selection rule with a calibrated threshold can
bound a failure rate in an environment where determinability is computable.**
It does not demonstrate that a language model can produce such a score from a
real conversation, which is the hard part of the deployment this is motivated
by.

The companion benchmark did measure a real model and found it answered
**62.5%** of undecidable cases. That number and this one are not comparable —
different cases, different n, and that model was scoring free text rather than
four known fields. Putting them in one table would be the most misleading
thing this repository could do.

**This is the most serious objection and nothing here fixes it.**

What does exist is a quantitative bound on how bad it gets, which is better
than a shrug. A language model's self-reported confidence fails in documented
ways — it clumps on round values and it orders imperfectly — and the
corruption study in [`results-secondary.md`](results-secondary.md) applies
both as fixed transforms of the score:

| | coverage | 10% tolerance |
|---|---:|---|
| the hand-written score | 72.9% | feasible always |
| rounded to tenths | **65.2%** | infeasible in 23% of trials |
| mild rank noise (Kendall τ = 0.755) | **40.4%** | **never feasible** |

So the honest extrapolation is not "it probably transfers". It is: **a
conformal abstention wrapper built on a badly-ordered confidence signal stays
safe and becomes close to useless**, and the only way to know which side a
real model falls on is to run one. That is still the thing to do next, and it
is still not done here.

## 2. The guarantee is supported, not proved

Calibration searches 101 thresholds and reports a bound valid for a threshold
fixed in advance. `docs/theory.md` states this plainly and measures what the
provable version costs: roughly three times the calibration data, which is not
available here.

Repeated validation is evidence. It is not a theorem, and a reviewer who wants
a theorem should read argument 2 of the theory document rather than the
headline.

## 3. The scorer excluded from the headline is better

The pre-registration named the handcrafted scorer as primary, on the reasoning
that it needs no fitting fold and so costs no calibration data.

Measured on holdout, the fitted scorer reaches **97.7% coverage at α = 0.10
against the handcrafted scorer's 74.8%**, with violations at 1.0% against
2.0%. The judgement was wrong and the pre-registration preserved the evidence
that it was made in advance rather than after seeing this.

Curiously the two score almost identically on ordering — AUC 0.9644 against
0.9631 on holdout. A one-point AUC difference producing a twenty-three point
coverage difference means the ordering that matters is entirely local to the
threshold, and AUC is the wrong summary for choosing between scorers here.
That is a defect in how this project selected its scorer.

Two later results say the same thing from different directions, which turns a
curiosity into a claim about the metric. The `sharpen` corruption is strictly
monotone, so it leaves AUC identical to the floating-point bit while moving
coverage by up to 3.8 points. And per-band AUC runs from 0.9345 to 0.9976 —
every band well ordered — while one band absorbs **4.12×** its share of the
error budget. **AUC is a ranking measure and every decision this method makes
is threshold-local; three independent results here show it cannot see the
difference.**

## 4. The guarantee it advertises is not the guarantee an applicant wants

An operator names α and the rule holds α **over the population**. Measured at
α = 0.20 on 672 cases: the budget is honoured overall in 98.5% of trials and
broken for some income band in **98.2%**. The lowest-income band runs at
**45.7%** unsafe.

Nothing about that is a bug, and §4 of [`theory.md`](theory.md) explains why a
distribution-free method cannot promise otherwise. But an applicant does not
experience a population. **A rule marketed as "name your tolerance and get it"
delivers something materially different to the people it most affects, and
this repository shipped that framing for four rounds before measuring it.**

Group-conditional calibration repairs it on these bands — worst band 45.7% to
12.9%, and coverage *up* rather than down — at a sample-size cost that makes
it infeasible at α = 0.10 on 672 cases. So the repair exists, it is cheap in
coverage and expensive in data, and it only covers the groups someone thought
to name.

## 5. Sixteen knowledge states is not an interview

Four fields, each known or unknown, gives sixteen states per case. A real
intake has dozens of fields, partial information, contradictory answers and
applicants who abandon. The companion `casefile` environment models some of
that and this one does not.

A rule that holds a tolerance over sixteen states says little about one over
a space large enough that the agent cannot enumerate it.

## 6. The oracle defines the truth being bounded

Determinability comes from PolicyEngine, an implementation of published SNAP
rules with its own defects. Where it is wrong, this bounds **agreement with a
wrong oracle** rather than correctness.

This is unavoidable without adjudicated ground truth, and it is the same
limitation the benchmark this derives from carries.

## 7. One benchmark, one domain

Everything is SNAP eligibility. Whether the construction transfers to tax,
immigration, prior authorisation or anything else is untested, and the feature
that does most of the work — distance from an income threshold — is domain
specific in an obvious way.

## 8. The holdout is 81 cases, and the replication is 672

Large enough to beat the seven-case split that forced the regeneration, and
small enough that a violation rate of 5.3% and one of 3.3% are not
distinguishable. The pre-registration's intervals were wide for this reason,
and the per-α numbers on that holdout are a shape rather than estimates.

Round four addresses this and the reader should weigh the replication rather
than the original: 672 cases, 400 trials, a fresh split of the **complete**
1,344-household enumeration, violations of 1.5% / 0.0% / 0.0% at
α = 0.20 / 0.15 / 0.10. What it does not address is that both benchmarks are
the same generator, the same four fields and the same oracle. **A replication
on more cases from the same space is not an independent test**, and the thing
it rules out is a lucky split rather than a wrong design.

---

## What survives

- **The unit-matching result.** Calibrating over states and deploying under a
  rule that selects states breaks the guarantee. That is measured, the
  mechanism is identified, and it does not depend on the scorer, the domain or
  the oracle being right.
- **The ordering.** Split first, method second, predictions third, holdout
  fourth, each in its own commit. Coverage rose from dev to holdout, which is
  what a method that was not tuned against its development set does.
- **The miss stayed a miss.** 5.3% against a 5% target is 0.19 standard
  errors and is recorded as a failed prediction. So did the other four: A2's
  monotonicity, C1 and C2 predicting the wrong band, and E6 predicting that
  group conditioning would cost coverage when it gains it.
- **The subgroup result.** It does not depend on the scorer being good — the
  scorer ranks at 0.9976 inside the band it fails on — nor on the domain, nor
  on the oracle being right. It depends only on using one threshold across
  groups whose score distributions are shifted, which is what every single
  threshold does.
- **The three bugs, and that scrutiny rather than validation found them.** The
  refusal threshold that was not a refusal, the subgroup comparison that
  measured itself, and the feasibility-conditioning the metric did not have.
  All three flattered the method. None was found by the experiment meant to
  validate it, and one was held in place by a passing test.

## The objection I cannot answer

Argument 1. No language model was run. The construction works where
determinability is computable, and the deployment it is motivated by is one
where it is not.
