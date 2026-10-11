# Decision assurance: abstain

Test calibrated questioning as an intake aid with mandatory escalation. Do not monetize an unsafe benefits commitment away: its maximum rate is a separate feasibility constraint.

**Evidence:** Oracle household states share household-level dependence. The corrected certification API applies simultaneous binomial bounds over a fixed threshold grid and abstains when infeasible.

**Uncertainty:** Oracle states are not observed applicant conversations. Zero monetized harm in this model means harm is governed by a hard gate, not that harm has no value.

## Robustness of the assumed business case

| Alternative | Feasible grid cases / 27 | Worst regret when feasible | Maximum volume at fixed review capacity |
|---|---:|---:|---:|
| Specialist review of every intake | 6 | $54,225.00 | 9000 |
| Calibrated questioning and escalation | 9 | $0.00 | 24000 |
| Fixed short intake without calibration | 0 | No feasible case | 89999 |

**Robust minimax choice:** None. No option is feasible across the entire stress grid.

Finite assumed grid, not a probability distribution or protection outside the grid. Conditional regret never overrides feasibility. Null robust option means no unconditional recommendation. Cost regret is relative to the cheapest feasible option in that same scenario. Failure counts can overlap.

## Missing-outcome sensitivity

| Outcomes masked per arm | Primary effect bounds | Incident effect bounds | Every completion clears margins? |
|---|---:|---:|---|
| 0% | [5.0%, 5.0%] | [1.2%, 1.2%] | False |
| 5% | [-0.9%, 9.1%] | [-3.8%, 6.2%] | False |
| 10% | [-6.1%, 13.9%] | [-9.0%, 11.0%] | False |
| 20% | [-16.6%, 23.4%] | [-19.1%, 20.9%] | False |

These are identification bounds on deliberately masked synthetic outcomes, not confidence intervals or measured missingness. Failures and non-starters remain in the assigned denominator. Passing this sensitivity check would still require statistical and domain-quality gates.

## Domain measurement contract

**Decision:** Choose when to stop questioning, continue, or send a case to specialist review.

**Primary outcome:** Wrong definitive eligibility decisions divided by all definitive decisions, reported jointly with definitive-decision coverage.

**Denominator:** All eligible assigned households for coverage; all definitive decisions for selective risk. Never mix these denominators.

**Independent unit:** Household; multiple states and questions from one household are dependent.

**Quality guardrail:** Simultaneous upper risk bound over the fixed candidate threshold grid; subgroup coverage and review load reported separately.

**Minimum required data:** Household ID, frozen policy and threshold-grid version, question history, definitive/abstain result, oracle or adjudicated label and provenance, review time.

**Missingness and failure handling:** Abstentions remain in the coverage denominator. Unknown truth prevents certification for the affected outcome; missing labels are not correct answers.

**Release rule:** Only certify when the documented calibration assumptions and prespecified risk ceiling hold; otherwise abstain. Synthetic activation cannot satisfy this gate.

**Reversal trigger:** Changed question policy, shifted eligible population, or inadequate calibration support requires recertification.

## Interview defense

**Why not maximize coverage?**

More definitive answers can conceal more harmful errors. I constrain risk first and then compare coverage and reviewer effort.

**What does the oracle establish?**

It establishes answers within the modeled household rules. It does not establish real applicant behavior or deployment exchangeability.

## Implementation handoff

1. Freeze the eligible population, denominator, outcome horizon and proposed decision owner before comparison.
2. Reconcile assignment and outcome records at the independence unit; classify missingness without deleting cases.
3. Estimate the domain outcome and its uncertainty separately from activation. Apply risk and capacity vetoes before comparing costs.
4. Record approve, hold, or reverse with the evidence version and violated gate. An unmeasured required domain gate means HOLD.

The supplied cluster-budget grid is a planning sensitivity check with assumed ICC. It is not an estimate from real clusters and does not guarantee joint power. No stakeholder approval or real experiment is asserted.
