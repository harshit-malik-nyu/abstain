# What every file in here is, and what it backs

Forty-one JSON files and a dozen logs accumulated over sixteen rounds, and
until this manifest existed a reader could not tell which of them back a
published claim, which script produces which, or which predate a bug fix that
changed what their numbers mean.

That was not a cosmetic gap. **Two numbered claims rested on files that no
script could regenerate and no test ever read**, and one of them — `11% of
trials violated a 5% target; calibrating on commitments takes it to 0%` —
turned out to be the vacuous zero this repository documents as its third bug,
in evidence added seven commits before the fix. It survived sixteen rounds
because nothing in the pipeline looked at those two files.

`tests/test_evidence_manifest.py` enforces what this file says: every JSON in
`evidence/` must be listed, every file marked **live** must have a producing
script and at least one test that reads it, and every file marked
**pre-correction** must still lack the conditioned metric, because
regenerating one would erase the record of what was wrong.

## The metric that changes meaning

`violation_rate` counts violations over **all** trials, including those where
calibration declined to issue a threshold. A condition that is 100%
infeasible therefore reports **0.0% violations**, which reads as a pass and is
not one. `violation_rate_when_feasible` conditions on the trials actually
certified and returns `None`, never `0.0`, when there are none.

The fix landed at commit 13. Files produced before it carry only the
unconditional field and are marked **pre-fix metric** below. A table built
from one can contain a vacuous zero, and two did.

## Live — backs a published claim

| file | written by | backs |
|---|---|---|
| `cases.json`, `cases.meta.json` | `build_cases.py` | the 79/81-case benchmark and its PolicyEngine version |
| `cases_fine.json`, `cases_fine.meta.json` | `build_cases.py` (CI) | the 1,344-household enumeration |
| `dev.json`, `holdout.json`, `*.sha256` | `split.py` | the original split, digest-locked in commit 1 |
| `fine_dev.json`, `fine_holdout.json`, `*.sha256` | `split.py` | the 672/672 split every current result uses |
| `holdout_result.json` | `open_holdout.py` | the holdout table, P1–P8 |
| `round4_dev.json`, `round4_holdout.json` | `run_round4.py` | the replication, E1–E8 |
| `secondary_dev.json` | `run_secondary.py` | the plug-in baseline and corruption study, A1–A4, B1–B4 |
| `corruption_postfix.json` | `rerun_corruption.py` | the corruption study after the refusal-threshold fix |
| `round5_shift.json` | `run_round5.py` | the shift sweep, F1–F5 |
| `recalibration.json` | `run_recalibration.py` | "just recalibrate", G1–G3 |
| `fitted_conditional.json` | `run_fitted_conditional.py` | the learned and no-distance scorers, H1–H4, J1–J4 |
| `plugin_scale.json` | `run_plugin_scale.py` | the plug-in at scale, K1–K4 |
| `materiality.json` | `run_materiality.py` | the materiality sweep, L1–L4 |
| `mechanism.json` | `diagnose_mechanism.py` | the three-pass mechanism account |
| `award_aware.json` | `run_award_aware.py` | M1–M5 |
| `signed_scorer.json`, `opening_state.json` | `run_signed.py`, `measure_opening_state.py` | N1–N4 and the fifth AUC result |
| `no_distance_groups.json` | `run_no_distance_groups.py` | O1–O5 |
| `partition_sweep.json` | `run_partition_sweep.py` | Q1–Q7 |
| `pool_bootstrap.json` | `run_pool_bootstrap.py` | R1–R5, pool-level uncertainty |
| `uncertainty.json` | `run_uncertainty.py` | the cluster bootstrap, ±9.5 against ±0.6 |
| `confounds.json` | `check_confounds.py` | the question-policy control |
| `allocation.json` | `run_allocation.py` | the question-allocation result |
| `unit_comparison.json`, `leakage.json`, `unit_populations.json` | `rerun_unit_and_leakage.py` | claim 2, **after its retraction**, and the three-populations table |

## Pre-correction — kept as the record of a defect

Not regenerated, by design. Each still carries the unconditional metric and
is the evidence of what a published figure was before it was corrected.

Two different reasons appear here and only one of them is about the metric,
so the table says which. A row marked **pre-fix metric** carries the
unconditional `violation_rate` and nothing else; a test requires those to stay
that way. The others are earlier runs of a *post*-fix experiment, kept so a
re-run or a relaunch is checkable rather than asserted.

| file | why it is kept | pre-fix metric |
|---|---|:--:|
| `unit_comparison-precorrection.json` | the "0%" that was zero violations in 100% infeasible trials | **pre-fix metric** |
| `leakage-precorrection.json` | the "11%" that was 11 of 100 trials with 76 infeasible | **pre-fix metric** |
| `secondary_dev_prefix.json` | the corruption study before the refusal-threshold fix | **pre-fix metric** |
| `round4_dev_prefix.json` | round four's run before its final commit, kept to show the numbers did not move | no |
| `round4-holdout-partial-interrupted.txt` | the interrupted holdout run, committed before the relaunch | no |
| `pool-bootstrap-interrupted.txt` | round R's first 32 draws, committed before the relaunch | no |

## Superseded — pre-fix metric, referenced by nothing

These are from the first six commits and **nothing in the repository reads
them** — not the README, the docs, a script or a test. They are kept because
deleting evidence is not this repository's habit, and listed here so no future
reader mistakes one for a current result. All carry the **pre-fix metric**.

| file | what it was |
|---|---|
| `validation_dev.json` | the first dev validation sweep, superseded by `round4_dev.json` |
| `search_correction.json` | the union-bound comparison; its figures are in `theory.md` §3 and the vacuous zeros there are now marked |
| `fitted_secondary.json` | the first fitted-scorer run, superseded by `fitted_conditional.json` |
| `dev_final.json` | a per-α summary superseded by `round4_dev.json` |
| `casefile_cases.json`, `oracle_table.json` | 16-case samples from building the oracle, kept as a worked example |
| `prediction_check.json` | the first automated P1–P8 scoring, superseded by `docs/predictions.md` |

## Run logs

`*-run.txt` is the stdout of the script that wrote the neighbouring JSON,
committed so a reader can see what the run printed rather than only what it
serialised. `*-interrupted.txt` and `*-partial-*.txt` are listed under
pre-correction above: they exist to make a relaunch checkable.
