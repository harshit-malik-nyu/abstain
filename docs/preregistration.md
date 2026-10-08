# Pre-registration

Written before the holdout was opened. The git history shows this commit
precedes any file that reads `evidence/holdout.json`.

---

## Why this exists

A holdout result is only worth its discipline. If I open the holdout, see a
number, and then describe what it means, there is no way for a reader to tell
whether the description was chosen to fit the number.

Writing the predictions down first makes the result interpretable either way.
If the method does what I said, the claim is supported. If it does not, that
is a finding and the prediction is the evidence that I did not expect it.

## The method, frozen

Nothing below changes after this commit.

| | |
|---|---|
| **Scorer** | `handcrafted_scorer` — no training step, nothing to leak |
| **Calibration** | `calibrate_on_trajectories` — unit matched to deployment |
| **Confidence** | δ = 0.05 (Clopper–Pearson) |
| **Budget** | 4 questions per case |
| **Opening state** | income known, everything else unknown |
| **Grid** | 101 points, uniform, pre-specified |

The fitted scorer is **excluded** from the headline. It scores better on
ordering (AUC 0.958 against 0.934) and it requires a disjoint fitting fold,
which costs a third of the calibration data at a sample size where the bound
is already the binding constraint. It is reported as a secondary result.

## Dev results, for reference

150 trials per tolerance, calibration and deployment disjoint per trial.

| α | Violations | Infeasible | Coverage | Questions/case |
|---:|---:|---:|---:|---:|
| 0.20 | 2.0% | 0% | 72.4% | 2.20 |
| 0.15 | 1.3% | 0% | 73.3% | 2.29 |
| 0.10 | 1.3% | 0% | 70.0% | 2.35 |
| 0.05 | 0.0% | **100%** | — | — |

α = 0.05 is infeasible at this calibration size and is reported as such.

---

## Predictions

Stated as intervals, because a point prediction on a sample this size would be
a guess dressed as a commitment.

### Primary — the guarantee holds

**P1.** At α = 0.10, the violation rate on holdout will be **at or below
0.05**, the confidence level the bound was calibrated at.

**P2.** At α = 0.20 and α = 0.15, the violation rate will also be at or below
0.05.

**P3.** At α = 0.05, calibration will be **infeasible in the majority of
trials**, because the holdout calibration fold is 48 cases and the
Clopper–Pearson floor at zero failures is 0.0607 there.

This is the claim. If P1 fails, the method does not deliver the knob it
advertises and the project's central result is negative.

### Secondary — the method is useful

**P4.** Coverage at α = 0.10 will be between **55% and 85%**. The dev figure
is 70.0% and the holdout is a different draw of 81 cases, so the interval is
wide on purpose.

**P5.** Questions per case at α = 0.10 will be between **1.9 and 2.8**,
against an oracle ceiling near 1.5 and asking-everything at 3.0.

**P6.** The rule will beat *answer immediately* on unsafe rate by more than
50 points and beat *ask everything* on coverage by more than 50 points, at
every feasible α.

### Shape

**P7.** Coverage will be **monotone non-increasing** in tightening α across
the feasible range. A method whose coverage rises as the tolerance tightens is
not doing what it claims.

**P8.** Questions per case will be **monotone non-decreasing** in tightening α.

---

## What would falsify the project

- **P1 fails.** The guarantee does not transfer to unseen cases. This is the
  outcome that matters; everything else is secondary to it.
- **P7 or P8 fails.** The tolerance knob does not control what it says it
  controls, and any single-α result is then a coincidence.
- **Coverage below 40% at every feasible α.** The rule would be safe and not
  useful, which is the `ask everything` policy with extra steps.

## What would not falsify it

- **P3 being wrong in either direction.** Feasibility at α = 0.05 depends on
  how many cases happen to commit, which varies with the draw.
- **Coverage outside P4's interval while P1 holds.** The guarantee is the
  claim; coverage is a property of the scorer and would be a reason to improve
  the scorer rather than to doubt the rule.

## Analysis plan

One run. 150 trials per tolerance, seed 3, the same code path as dev with
`evidence/holdout.json` substituted for `evidence/dev.json`.

No tuning after opening. If the result is bad, it is reported bad.
