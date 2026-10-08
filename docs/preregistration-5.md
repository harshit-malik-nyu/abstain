# Pre-registration, round five — breaking the assumption on purpose

Written before `src/abstain/shift.py` exists. The git history shows it.

---

## The gap this closes

Every guarantee in this repository rests on exchangeability: the deployed cases
are drawn like the calibration cases. `rule.py` says so, `validate.py` says it
cannot test it, `docs/theory.md` lists it as an assumption, and the README
points at a sibling project for what happens when it breaks.

**Nothing here measures it.** The project's central caveat is asserted and
never priced, which means a reader has no way to know whether the assumption
is a technicality or the whole ballgame.

It is cheap to measure, and the apparatus is already built. The income bands
partition the benchmark, round four established that the bands behave very
differently — `well-below` runs at 45.7% unsafe against a pooled 11.1% at
α = 0.20 — so **re-weighting the bands between calibration and deployment is a
realistic covariate shift with a known mechanism.** A benefits agency whose
applicant mix shifts toward the lowest-income band is not a hypothetical.

## The design

Calibrate on the natural band mix. Deploy on a mix where `well-below`'s share
is forced to **p**, sweeping p from its natural 14.3% to 100%. Everything else
— scorer, grid, δ, trials, the rule — is unchanged.

| | |
|---|---|
| **Set** | `evidence/fine_dev.json`, 672 cases |
| **Shift** | `well-below` share of the deployment fold ∈ {0.143, 0.25, 0.40, 0.60, 0.80, 1.00} |
| **Calibration** | natural mix, unshifted, every condition |
| **Schemes** | pooled · by-band |
| **α** | 0.20, 0.15 |
| **Trials** | 300 per condition |
| **Seed** | 41 |

Deployment folds are built by resampling the deployed cases to hit the target
share. That changes the deployment fold's size, so questions-per-case and
coverage are reported but the violation rate is the quantity of interest.

Calibration is held at the natural mix in every condition deliberately. The
operator does not know the shift is coming — that is what makes it a shift
rather than a different problem.

---

## Predictions

**F1.** At p = 0.143, the natural share, the pooled rule's violation rate will
be **at or below δ**. This is the control; if it fails, the resampling harness
is broken and nothing below means anything.

**F2.** The pooled rule's violation rate will **rise monotonically in p**.

**F3.** At p = 1.00 — deploying only on `well-below` — the pooled rule will
violate in **more than 80% of trials** at α = 0.20. The threshold was
calibrated for a mix where that band is 14.3% of cases, and the band's own
unsafe rate under that threshold is 45.7%, which is more than double the
tolerance.

**F4.** **Group-conditional calibration will be substantially robust to this
shift**: its violation rate at p = 1.00 will stay at or below δ, and in any
case below a fifth of the pooled rule's at the same p.

F4 is the prediction worth the round. Under group conditioning each band gets
its own threshold, so **re-weighting the bands changes which thresholds get
used and not what any threshold is.** The guarantee becomes invariant to shifts
in group proportions, because it was never a statement about the mixture in the
first place.

If F4 holds, two findings that looked separate are one finding:

> Group-conditional calibration is not only a fairness repair. It is the
> construction that makes the guarantee survive a shift in who shows up — and
> the subgroup that absorbs the budget is exactly the subgroup whose
> over-representation breaks the pooled rule.

That is a real reason to pay its costs, and it is stronger than "the pooled
number was misleading".

**F5.** The pooled rule's **reported bound will not move** as p rises. It is
computed on calibration data, which is unshifted, so the certificate stays
confident while the deployed rate degrades. A guarantee that fails silently is
worse than one that fails loudly, and this is the check on which this one does.

---

## What would falsify this round

- **F1 fails.** The harness is wrong. Nothing else is interpretable.
- **F4 fails.** Group conditioning does not buy shift robustness, the unifying
  claim above is withdrawn, and group conditioning goes back to being a
  fairness repair with a feasibility cost.

## What would not falsify it

- **F2 non-monotone at one step.** 300 trials and six shift levels; one
  inversion is noise, a reversal across the range is not.
- **F3 landing below 80%.** It is a magnitude guess about one band under one
  threshold.

## What this round does *not* establish

That the method is safe under distribution shift. It is not, and F3 is the
measurement of how unsafe.

What F4 would establish is narrower and worth stating precisely: the guarantee
is invariant to **shifts in the proportions of groups that were calibrated
separately.** It says nothing about a shift *within* a band, a new band that
calibration never saw, or a change in the relationship between the score and
determinability. Those break group conditioning exactly as they break the
pooled rule, and `group.threshold_for` already refuses to serve a group
calibration never saw rather than borrowing another group's threshold.

Conformal prediction under distribution shift has a literature — weighted
conformal methods for covariate shift, among others — and this round
implements none of it. It measures what the unweighted method costs when its
assumption is false, which is the thing a reader of this repository needs and
does not have.

## Analysis plan

One run on `fine_dev`, written to `evidence/round5_shift.json`. **The fine
holdout is not touched by this round** — round four's confirmatory run is the
only thing it carries.

No tuning. Misses reported as misses, pinned by test.
