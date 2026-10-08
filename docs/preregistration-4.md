# Pre-registration, round four — a powered benchmark and a replication

Written after `evidence/fine_dev.json` and `evidence/fine_holdout.json` were
built and split, and **before anything was run on either**. The git history
shows the split commit precedes this one and that no script reading either
file exists yet.

---

## Why there is a fourth round

Round three could not answer its question. The reason was not the method and
not the analysis: the benchmark was too small on both sides, and
`src/abstain/power.py` works out by how much. Round four is the same question
on a benchmark built to answer it, plus the replication that becomes possible
once the data exists.

## The benchmark

| | |
|---|---|
| **Source** | `evidence/cases_fine.json` |
| **Size** | 1,344 cases |
| **What it is** | the **complete enumeration** of the household space, not a sample of it |
| **Grid** | income every 3,000 from 0 to 60,000 (21 values) × 4 dependent counts × 4 ages × 4 states |
| **Oracle** | `policyengine-us==2.33.0`, recorded in `evidence/cases_fine.meta.json` |
| **Split** | 672 / 672, seed 20261008, stratified by income band |
| **Digests** | dev `e857bb2d…`, holdout `f796fee1…` |

Three things worth drawing out.

**It is the whole space.** Ten incomes by four by four by four is 640
households, so the original 160-case benchmark was a sample of a quarter of
one grid. Refining income to every 3,000 gives 1,344, and all 1,344 are built.
There is no sampling variation in the benchmark itself — only in the
dev/holdout split and in the per-trial draws.

**The refinement contains the original grid.** Every one of the ten original
income values is a multiple of 3,000, so the coarse benchmark's households are
a subset of this space. The two are the same population at different
resolutions rather than different populations, which is what makes a
replication meaningful rather than a change of subject.

**The band shares moved, and they are what they are.** A uniform income grid
over a fixed range gives `well-below` 14.3%, `near-threshold` 28.6%, `above`
19.0%, `well-above` 38.1%. The band boundaries come from the first commit and
are not adjusted to balance this; the power analysis uses the real smallest
share rather than a convenient one.

## The design, and the one parameter that is not inherited

| | |
|---|---|
| **Trials** | **400** per condition |
| **Calibration share** | **0.30** |
| **δ** | 0.05 |
| **Seed** | 31 |
| **Primary tolerances** | α = 0.20, 0.15 |
| **Exploratory tolerance** | α = 0.10 — underpowered here, by 1.23× |

**Trials rise from 150 to 400** because they are now cheap and the test is
tighter than the slack 150 allows. At 150 trials the standard error on a 5%
violation rate is 1.8 points, so the two-standard-error acceptance band runs
to 8.6% — wide enough that a genuinely failing procedure could pass. At 400 it
is 1.1 points and the band is 7.2%. Pre-specified here, not chosen after
seeing a result.

**The calibration share drops from 0.60 to 0.30**, and this is the decision
that makes the round possible. Group conditioning inflates the *deployment*
requirement far harder than the calibration one: a per-band rate has to be
resolvable in every band, so the deployment fold needs cases in the smallest
band. From `power.py`, at δ = 0.05 and a smallest band of 14.3%:

| α | cal/band | dep/band | needed at share 0.60 | needed at share 0.30 |
|---:|---:|---:|---:|---:|
| 0.20 | 14 | 22 | 385 | 327 |
| 0.15 | 19 | 40 | 700 | 443 |
| 0.10 | 29 | 89 | **1,558** | **890** |

At the inherited 0.60 share, α = 0.10 would need 1,558 cases and the whole
benchmark is 1,344. At 0.30 it needs 890. Dev and holdout are 672 each, so
0.20 and 0.15 are covered and **0.10 is 1.23× short** — which is why it is
labelled exploratory below rather than quietly reported in the same table.

A share chosen to make the data sufficient would be tuning. This one is
chosen from a closed-form requirement computed before the data was split,
it is a single value used at every tolerance and by every scheme, and the
shortfall it does not fix is declared.

---

## Predictions

### Primary — the headline result replicates

**E1.** The pooled rule's violation rate on **feasible** trials will be at or
below δ = 0.05 at α = 0.20, 0.15 and 0.10, on `fine_dev` and then on
`fine_holdout`.

This is the first replication of the project's central claim on an
independent, larger, freshly split benchmark. The original holdout was 81
cases; this is 672. If E1 holds, the claim rests on something other than one
lucky draw. If it fails, the original result was the draw and the project's
headline is withdrawn.

**E2.** Coverage at α = 0.10 will be between **60% and 85%**. The coarse
holdout gave 75.3%. The interval is wide because the band mix has changed —
`well-above` is 38.1% of this benchmark against 20.3% of the coarse one, and
those cases are mostly decidable, so coverage could legitimately rise.

### Primary — the concentration is real, and group conditioning fixes it

**E3.** On `fine_dev` at α = 0.20 and 0.15, the pooled rule will show
**concentration above 1.5** in at least one band: some band's share of unsafe
commitments will exceed 1.5× its share of deployments. This is experiment C's
finding, re-measured where it can be measured.

**E4.** Group-conditional calibration (`by-band`) will be **feasible in the
majority of trials** at α = 0.20 and 0.15. At 202 calibration cases and a
14.3% smallest band, that band gets about 29 cases, which clears the
Clopper–Pearson floor for both tolerances (14 and 19).

**E5.** Group-conditional calibration will bring the **worst band's unsafe
rate under α** in at least 95% of feasible trials, against a pooled rule that
does so less often. This is D1 restated for a design that can test it, and it
is the claim the module was written for.

**E6.** Group-conditional calibration will **cost coverage** relative to
pooled, at matched α and on the same trials. Four thresholds chosen
conservatively abstain more than one. The size of the gap is the price of
conditional validity and is the number worth reporting.

### Secondary

**E7.** `separate-well-below`, the two-group scheme, will sit **between**
pooled and `by-band` on both the worst-band rate and coverage. Still post-hoc,
still labelled.

**E8.** Which band concentrates will be **the same band** on `fine_dev` as
experiment C found on the coarse dev — `well-below`. If a different band
concentrates, the mechanism in `docs/preregistration-3.md` is wrong or is
specific to the coarse grid, and either way the diagnosis needs rewriting.

### Exploratory, and underpowered

**E9.** Everything above, at α = 0.10. Reported with the shortfall stated
(1.23× on cases, and the smallest band holds about 67 deployed cases against
the 89 needed). A pass here is weak evidence and a failure is weak evidence;
it is run because the number is interesting and omitting it after computing
that it would be underpowered would be choosing which numbers to show.

---

## What would falsify this round

- **E1 fails.** The central claim does not replicate. The project's headline
  result is withdrawn and the README says so above the fold.
- **E5 fails while E4 holds.** Group conditioning is feasible and does not fix
  the concentration. Then the diagnosis — shifted score levels under one
  global threshold — is wrong, and `group.py` is a fix for a
  mischaracterised problem.
- **E3 fails.** There is no concentration to fix on this benchmark, and
  experiment C's finding was specific to 79 cases. Then round three and round
  four are both answering a question that does not arise, and the honest
  report is that the subgroup problem was a small-sample artefact.

## What would not falsify it

- **E2, E6, E7 outside their intervals.** Cost and shape predictions.
- **E9 in any direction.** Declared underpowered in advance.
- **E8 failing.** It would mean the diagnosis is grid-specific, which is a
  finding about generality rather than about validity.

## Analysis plan

Two runs, in this order.

1. **`fine_dev`.** All schemes, all tolerances. Written to
   `evidence/round4_dev.json`.
2. **`fine_holdout`**, once. Same code path, same seed, `fine_dev` swapped for
   `fine_holdout`. Written to `evidence/round4_holdout.json`.

`fine_holdout` is opened **once**. The coarse benchmark's holdout
(`evidence/holdout.json`) is **not touched by this round at all** — it has
been opened twice already and its remaining value is as the record of the
original result.

No tuning between the two runs. A prediction that misses is reported as a
miss, with a test pinning the miss so a later edit cannot quietly drop it.
