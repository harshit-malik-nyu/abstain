# A selection rule that bounds how often an agent answers blind

## The failure this exists to fix

A companion benchmark measured a frontier model conducting benefits intake
interviews. Given cases that **cannot be decided** from the information
available, it answered anyway **62.5%** of the time. Downstream, each of those
is a filed claim built on a guess.

The reference policies bracket the problem:

| Policy | Unsafe | Wasted questions | Questions/case |
|---|---:|---:|---:|
| Answer immediately | **91.7%** | 0% | 0.00 |
| Ask everything | 0% | **44.4%** | 3.00 |
| Abstain if anything unknown | 0% | 0% | — resolves nothing |
| Oracle ceiling | 0% | 0% | **1.67** |

Each degenerate policy fails differently. Safety is free if you refuse to act;
coverage is free if you never check. **The open question is whether a rule can
hold a stated unsafe rate while resolving materially more than the safe
heuristic.**

## What the validation found

The method's claim is that an operator names a tolerance and gets it. A single
run cannot test that — a procedure violating its bound a third of the time
still looks fine on any given draw. So the bound is validated by repetition:
draw a calibration set, calibrate, deploy on disjoint cases, count violations.

**Two failures surfaced, and the second is the interesting one.**

### Leakage, as expected

A scorer fit on the whole pool and then validated on splits of that pool
violated a 5% target in **40%** of trials. Refitting on a fold disjoint from
both calibration and deployment cut it to **11%**.

That is the conformal argument working as advertised: it requires the score to
be fixed with respect to the calibration and deployment data, and a score fit
on them is not.

### The agent's own stopping rule breaks exchangeability

The remaining 11% was not leakage. Calibration observed every knowledge state
uniformly; the rule commits at the **first** state to clear the threshold,
which is selected by construction. At a threshold of 0.82:

| | States | Undetermined |
|---|---:|---:|
| Calibration population | 1,264 | **80.3%** |
| States the rule visits | 314 | 57.0% |
| States it **commits at** | 55 | **0.0%** |

Calibrating on the first distribution and deploying under the third destroys
the exchangeability the guarantee needs. **This is the same failure
`knowing-when-to-doubt` measures when a human reviewer routes on model
confidence — there the router is a person, here it is the rule itself, and the
mechanism is identical.**

### The fix, and what it costs

Make the calibration unit the deployment unit: for each candidate threshold,
run the rule on calibration cases and count the ones where it committed while
undecidable. Violations go to **0%**.

It costs sample size. Cases are fewer than states, so the finite-sample bound
is looser, and the tightest honest tolerance becomes a function of how many
cases the operator can calibrate on:

| Cases committed | Tightest achievable α |
|---:|---:|
| 40 | 0.072 |
| 60 | 0.049 |
| 100 | 0.029 |
| 200 | 0.015 |

On the dev calibration fold — 47 cases — α = 0.05 is **infeasible and reported
as such**. Reaching it needs 59 committed cases; α = 0.02 needs 149.

That is not a flaw in the method. It is the price of calibrating on the unit
that is deployed, stated rather than hidden by calibrating on a unit that
gives tighter numbers and a broken guarantee.

## The holdout result

Opened once, after the method was frozen and the predictions committed. The
git history shows that ordering.

**81 cases, 150 trials per tolerance, disjoint calibration and deployment
each trial.**

| α | Violations | Infeasible | Coverage | Questions/case |
|---:|---:|---:|---:|---:|
| 0.20 | 1.3% | 0% | 81.5% | 2.18 |
| 0.15 | **5.3%** | 0% | 80.2% | 2.26 |
| 0.10 | 3.3% | 0% | 75.3% | 2.37 |
| 0.05 | — | **100%** | — | — |

### Against the pre-registered predictions

| | Prediction | Result | |
|---|---|---|---|
| **P1** | violation at α = 0.10 ≤ 0.05 | **0.033** | held |
| **P2** | violation at α = 0.20 and 0.15 ≤ 0.05 | 0.013 / **0.053** | **missed** |
| **P3** | α = 0.05 infeasible in most trials | 100% | held |
| **P4** | coverage at α = 0.10 in [0.55, 0.85] | 0.753 | held |
| **P5** | questions at α = 0.10 in [1.9, 2.8] | 2.37 | held |
| **P6** | beats both degenerate policies by 50pp | yes | held |
| **P7** | coverage monotone as α tightens | 0.815, 0.802, 0.753 | held |
| **P8** | questions monotone as α tightens | 2.18, 2.26, 2.37 | held |

**Seven of eight held. The miss is reported as a miss.** At α = 0.15 the
violation rate came in at 5.3% against a 5% target — **0.3 points over, which
is 0.19 standard errors at 150 trials.** That is consistent with noise and it
is still a miss, and calling it one is cheaper than explaining it away.

### What the method does

At α = 0.10, against the two degenerate policies on the same 81 cases:

| | Unsafe | Coverage |
|---|---:|---:|
| Answer immediately | **92.6%** | — |
| Ask everything | 0% | **0%** |
| **The rule** | **2.5%** | **80.2%** |

### The number that matters most

**Coverage rose from dev to holdout — 70.0% to 75.3%.** A method tuned against
its development set degrades on unseen data. This did not, which is the
clearest evidence available that the holdout stayed shut.

## The scorer I excluded was better

The pre-registration named the handcrafted scorer as primary, reasoning that
it needs no fitting fold and so costs no calibration data. Measured on
holdout, refit per trial on a disjoint fold:

| Scorer | α | Violations | Coverage | Questions/case |
|---|---:|---:|---:|---:|
| Handcrafted | 0.10 | 2.0% | 74.8% | 2.37 |
| **Fitted** | 0.10 | **1.0%** | **97.7%** | 2.39 |
| Handcrafted | 0.20 | 0.0% | 81.4% | 2.18 |
| **Fitted** | 0.20 | 2.0% | **93.8%** | 2.05 |

**The judgement was wrong.** The pre-registration is what preserves the
evidence that it was made in advance rather than after seeing this.

One detail worth more than the result: the two score almost identically on
ordering — **AUC 0.9644 against 0.9631**. A one-point AUC difference producing
a twenty-three point coverage difference means the ordering that matters is
entirely local to the threshold, and **AUC is the wrong summary for choosing
between scorers here.** That is a defect in how this project selected its
scorer, not a detail.

## What is guaranteed, and on what basis

Three claims, resting on different things. [`docs/theory.md`](docs/theory.md)
separates them.

**The Clopper–Pearson bound is exact** for a threshold fixed in advance. Not
novel, not in doubt.

**The calibration unit must match the deployment unit** — measured, with the
mechanism identified.

**The deployed rule holds its tolerance — empirically supported, not proved.**
Calibration searches 101 thresholds and reports the bound at whichever it
stops on, and that bound is valid marginally for a threshold fixed in advance.
The construction does not deliver the statement; repeated validation does, and
the difference is worth keeping visible.

A union bound over the grid restores a provable simultaneous statement and is
**unaffordable here** — 100% infeasible at α = 0.10, because the data
requirement roughly triples:

| Target α | Marginal | Simultaneous |
|---:|---:|---:|
| 0.10 | 29 cases | **73** |
| 0.05 | 59 cases | **149** |

The calibration fold is 47. **`correct_for_search=True` turns the proof on for
anyone with three times the data.**

## The case against

[`docs/against.md`](docs/against.md) lists seven objections, leading with the
one that cannot be answered: **no language model was run.** The rule is
evaluated against an oracle-backed simulation where determinability is
computable, and the deployment it is motivated by is one where it is not.

The companion benchmark measured a real model answering **62.5%** of
undecidable cases. That number and these are **not comparable** — different
cases, different n, and that model scored free text rather than four known
fields. Putting them in one table would be the most misleading thing this
repository could do, so it does not.

## Status

Built, validated, pre-registered, and tested once on held-out data. The result
stands as reported, including the prediction that missed and the scorer choice
that was wrong.

## The holdout is locked before the method exists

The failure mode of a method paper is tuning against the evaluation until it
wins. It is rarely deliberate — it happens one reasonable decision at a time.

So the split is the first commit. The git history is the evidence that it
precedes every line of method code.

| | Cases | Composition |
|---|---:|---|
| **dev** | 8 | built on, tuned on, looked at freely |
| **holdout** | 8 | opened once, when the method is final |

Stratified by the share of each case's knowledge states that are
underdetermined, so both halves carry comparable mixes rather than one
collecting the decidable problems.

Each half ships a SHA-256. A later run producing different contents is visible
rather than silent, and `tests/` asserts the committed digests still match.

**A result on dev is a demonstration. A result on holdout is a result.**

## License

MIT. Derived from the `underdetermined` benchmark in the same account.
