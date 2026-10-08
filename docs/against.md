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

## 4. Sixteen knowledge states is not an interview

Four fields, each known or unknown, gives sixteen states per case. A real
intake has dozens of fields, partial information, contradictory answers and
applicants who abandon. The companion `casefile` environment models some of
that and this one does not.

A rule that holds a tolerance over sixteen states says little about one over
a space large enough that the agent cannot enumerate it.

## 5. The oracle defines the truth being bounded

Determinability comes from PolicyEngine, an implementation of published SNAP
rules with its own defects. Where it is wrong, this bounds **agreement with a
wrong oracle** rather than correctness.

This is unavoidable without adjudicated ground truth, and it is the same
limitation the benchmark this derives from carries.

## 6. One benchmark, one domain

Everything is SNAP eligibility. Whether the construction transfers to tax,
immigration, prior authorisation or anything else is untested, and the feature
that does most of the work — distance from an income threshold — is domain
specific in an obvious way.

## 7. The holdout is 81 cases

Large enough to beat the seven-case split that forced the regeneration, and
small enough that a violation rate of 5.3% and one of 3.3% are not
distinguishable. The pre-registration's intervals were wide for this reason,
and a reader should treat the per-α numbers as a shape rather than as
estimates.

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
  errors and is recorded as a failed prediction.

## The objection I cannot answer

Argument 1. No language model was run. The construction works where
determinability is computable, and the deployment it is motivated by is one
where it is not.
