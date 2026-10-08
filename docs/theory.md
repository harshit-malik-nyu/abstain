# What is guaranteed, and on what basis

Three claims appear in this repository. They rest on different things and are
separated here because conflating them is the easiest way to overstate the
result.

---

## 1. The Clopper–Pearson bound is exact

For a threshold **fixed in advance**, with `k` unsafe commitments out of `n`,

> P(true unsafe rate > CP_upper(k, n, δ)) ≤ δ

This is a standard exact binomial interval. Nothing here is novel and nothing
here is in doubt. It is why the threshold is chosen against the bound rather
than against the empirical rate — a threshold tuned to hit α on the sample
sits above α half the time.

**Status: proved, and not by me.**

## 2. The calibration unit must match the deployment unit

Calibrating over knowledge states uniformly and deploying under a rule that
commits at the first state to clear the threshold breaks exchangeability. At
a threshold of 0.82 on dev:

| | States | Undetermined |
|---|---:|---:|
| Calibration population | 1,264 | 80.3% |
| States the rule visits | 314 | 57.0% |
| States it commits at | 55 | 0.0% |

Measured consequence: 11% of trials violated a 5% target, with the scorer
refit on a disjoint fold so leakage is excluded. Calibrating on commitments
instead takes it to 0%.

**Status: measured, and the mechanism is the one
`knowing-when-to-doubt` identifies for human routers.** The agent's stopping
rule plays the role the reviewer plays there.

## 3. The deployed rule holds its tolerance

This is the claim the method advertises and **it is not proved.**

`calibrate_on_trajectories` searches 101 thresholds and reports the bound at
whichever it stops on. The bound is valid marginally, for a threshold fixed in
advance, and this threshold is selected using the data the bound is computed
on. The construction therefore does not deliver the statement.

### What supports it instead

Repeated validation. Fresh calibration and deployment sets, disjoint, 150
trials per tolerance:

| | α = 0.20 | α = 0.15 | α = 0.10 |
|---|---:|---:|---:|
| dev | 2.0% | 1.3% | 1.3% |
| **holdout** | **1.3%** | **5.3%** | **3.3%** |

Pre-registered before the holdout was opened; seven of eight predictions held
and the miss (5.3% against a 5% target, 0.19 standard errors) is recorded as
a miss.

**Status: empirically supported, not proved. That is weaker and it is what
the evidence is.**

### The provable version, and what it costs

A union bound over the grid — testing each candidate at δ/101 — restores a
valid simultaneous statement. Measured on dev it is unaffordable here:

| α | Violations | Infeasible | Coverage |
|---:|---:|---:|---:|
| 0.20 | 0.0% | **55%** | 66.5% |
| 0.15 | 0.0% | **100%** | — |
| 0.10 | 0.0% | **100%** | — |

Because the requirement roughly triples:

| Target α | Cases for the marginal bound | Cases for the simultaneous bound |
|---:|---:|---:|
| 0.20 | 14 | 35 |
| 0.15 | 19 | 47 |
| 0.10 | 29 | **73** |
| 0.05 | 59 | **149** |

The calibration fold here is 47 cases. So α = 0.10 is affordable marginally
and not simultaneously, by about a factor of three.

**The proof is available to anyone with three times the calibration data, and
`correct_for_search=True` turns it on.** Nothing about the method changes —
only the level each candidate is tested at, and how much data is required to
pass.

---

## What none of this covers

**Correctness.** The bound is on answering while undecidable. A case can be
decidable and the agent still wrong, and nothing here constrains that.

**Distribution shift.** Every validation draws calibration and deployment from
one pool, which is exactly the exchangeability the argument assumes.
`knowing-when-to-doubt` measures what happens when deployment differs and
finds the guarantee fails — this project does not re-measure it.

**The oracle.** Determinability comes from PolicyEngine, an implementation of
published rules with its own defects. Where it is wrong, this bounds agreement
with a wrong oracle.
