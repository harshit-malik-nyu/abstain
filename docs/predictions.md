# Every prediction, and what happened

Seventy-three predictions across nine pre-registrations, each written before the
code that tested it. This table is the whole record: no prediction is omitted,
and the outcome column is the one that was true at the time, not the one that
would read best.

**Scoring rule, fixed and applied even where it hurts: a prediction is scored
against the number written down**, not against the nearest figure that would
let it pass. M3 is the case that tests this — see below.

`tests/test_predictions.py` parses this file, counts the outcomes, and
requires the counts quoted anywhere else to match. A hand-counted number in
prose goes stale silently — the opening of the README said "five misses" when
there were ten — so the number is derived from here rather than written twice.

| | Prediction | Outcome | |
|---|---|---|---|
| **P1** | violation at α = 0.10 ≤ δ on holdout | 3.3% | held |
| **P2** | violation at α = 0.20 and 0.15 ≤ δ | 1.3% / **5.3%** | **missed** |
| **P3** | α = 0.05 infeasible in most trials | 100% | held |
| **P4** | coverage at α = 0.10 in [0.55, 0.85] | 0.753 | held |
| **P5** | questions at α = 0.10 in [1.9, 2.8] | 2.37 | held |
| **P6** | beats both degenerate policies by 50pp | yes | held |
| **P7** | coverage monotone as α tightens | 0.815 → 0.753 | held |
| **P8** | questions monotone as α tightens | 2.18 → 2.37 | held |
| **A1** | plug-in violates δ at every α | 16.7–20.7% | held |
| **A2** | plug-in violations rise as calibration shrinks | 16.7% at n=40, 20.7% at n=50 | **missed** |
| **A3** | conformal holds δ at every calibration size | 0.7–3.3% | held |
| **A4** | plug-in has higher coverage than conformal | 70.8% vs 67.5% | held |
| **B1** | bound holds for every corruption | no violation when feasible | held *(after a bug fix; failed as first run)* |
| **B2** | `sharpen` within 5pp of `identity` on coverage | +0.8 to +3.8pp | held |
| **B3** | coverage monotone in noise σ | monotone, but via infeasibility | held *(trivially — see below)* |
| **B4** | `constant` and `inverted` fail by infeasibility | 100% infeasible | held *(after the same fix)* |
| **C1** | budget concentrates on `near-threshold` | it took **zero**; `well-below` took 3.44× | **missed** |
| **C2** | coverage lowest in `near-threshold` | lowest in `above` | **missed** |
| **C3** | some band over α while pooled is under | False on 79 cases, **True** on 672 | **missed, then held when powered** |
| **D1–D5** | group conditioning on 79 cases | **untestable** — see below | withdrawn |
| **E1** | guarantee replicates on the fine benchmark | 0.0 / 1.8 / 0.0% | held |
| **E2** | coverage at α = 0.10 in [0.60, 0.85] | 0.778 | held |
| **E3** | concentration above 1.5 in some band | 4.24 | held |
| **E4** | group conditioning feasible in most trials | 370/400 | held |
| **E5** | worst band under α in ≥95% of feasible trials | 96.5% | held |
| **E6** | group conditioning **costs** coverage | it **gains** 4.7pp | **missed** |
| **E7** | two-group scheme sits between the other two | 69.5% vs 99.8% and 3.5% | held |
| **E8** | same band concentrates as on dev | `well-below` both | held |
| **F1** | control holds at the natural mix | 0.7% | held |
| **F2** | pooled violations monotone in shift | monotone at both α | held |
| **F3** | pooled violates in >80% of trials at full shift | 98.0% | held |
| **F4** | group conditioning robust to the shift | ≤0.7% at every level | held |
| **F5** | the reported bound does not move | 0.175 at all six | held |
| **G1** | recalibration restores δ at every shift level | holds at 3 of 6; 8.0 / 12.7 / 9.3% | **missed** |
| **G2** | conditioning still holds coverage after recalibration | +3.7 to +4.0pp | held |
| **G3** | recalibrated pooled rule still concentrates | 45.1%, 4.03× | held |
| **H1** | a learned scorer also concentrates | 3.31× | held |
| **H2** | the same band is worst | `well-below` | held |
| **H3** | fitted pooled rate ≤ handcrafted | 11.8% vs 11.1% | **missed** |
| **H4** | conditioning fixes the learned scorer too | 86.5% → 7.0% | held |
| **J1** | a no-distance scorer still concentrates | **1.72×, nothing hidden** | **missed** |
| **J2** | the same band is still worst | `well-below` | held |
| **J3** | no-distance coverage below 60% | **92.7%** | **missed** |
| **J4** | no-distance AUC below 0.80 | 0.8888 | **missed** |
| **K1** | plug-in violations fall monotonically with calibration size | rises again, 8.7% → 16.0% | **missed** |
| **K2** | plug-in holds δ at 400 calibration cases | 16.0% and 6.3% | **missed** |
| **K3** | plug-in violates >15% at the smallest fold | 36.3% | held |
| **K4** | conformal holds δ at every size | 0.3–2.3%, declining where it cannot | held |
| **L1** | concentration above 2× from $25 to flip-only | 4.07–4.11 up to $500, **1.55** at flip-only | **missed** |
| **L2** | `well-below` worst at every setting | worst becomes `above` at flip-only | **missed** |
| **L3** | flip-only concentration at least as large as $50 | **1.55 against 4.07** | **missed** |
| **L4** | materiality $0 degenerates the benchmark | 57.3% open, 75.7% coverage — not degenerate | **missed** |
| **M1** | the award term drops concentration below 2.0 | **4.07 — identical to its control** | **missed** |
| **M2** | without the coverage collapse blinding caused | 75.8% | held *(vacuously — see below)* |
| **M3** | pooled rate at or below the handcrafted 11.1% | 11.5%, equal to its control to every digit | **missed** |
| **M4** | `well-below` stops being the worst band | still worst | **missed** |
| **M5** | conditioning helps **less** than before | helps by exactly as much, 46.5% → 13.7% | **missed** |
| **N1** | the signed term genuinely reorders states | 3.04% of reachable pairs | held *(and the wrong guard)* |
| **N2** | reordering drops concentration below 2.5 | **4.07 — identical again** | **missed** |
| **N3** | `well-above` rises by at most 3 points | **0.00** points | held *(vacuously)* |
| **N4** | coverage stays above 68% | 76.0% | held *(vacuously)* |
| **Q1** | a band still exceeds α under a **neutral** equal-count partition | 27.3% against 20% | held |
| **Q2** | and it is the poorest quartile | `q1-poorest` | held |
| **Q3** | its concentration is above 2.0 | 2.46 | held |
| **Q4** | concentration falls monotonically as the bottom cutoff rises | 4.83 → 4.13 → 3.76 → 3.05 → 2.46 | held |
| **Q5** | a 3k cutoff concentrates **more** than the published 6k | **4.83 against 4.13** | held |
| **Q6** | two bands at the median show concentration below 2.0 | 1.42, **and hides nothing** | held |
| **Q7** | eight bands localise further than four | **4.13, identical** | **missed** |
| **O1** | the no-distance scorer breaks a 10% budget for some band | **3.79%, nothing hidden** | **missed** |
| **O2** | its worst-band rate at α = 0.10 is within 2 points of its rate at 0.20 | 3.79% against 12.48% | **missed** |
| **O3** | conditioning still fixes what is left at α = 0.10 | **feasible in 0 of 200 trials** | **missed** |
| **O4** | conditioning costs feasibility at α = 0.10 | 0 of 200 | held |
| **O5** | `well-below` stays worst at every tolerance | all three | held |

---

## The ones that need a sentence

**P2** came in 0.3 points over a 5% target, which is 0.19 standard errors at
150 trials. Consistent with noise and still a miss.

**B1 and B4 failed as first run**, and the failure was a safety bug rather
than the theory: the threshold calibration falls back to when it declines to
certify itself was reachable. Both runs are kept in `evidence/`; the fix is
described in the README.

**B3 passes without testing what it was meant to test.** Coverage is monotone
in σ, but it reaches zero through infeasibility rather than gradual
degradation. Read it as a near-miss.

**C3 is the most instructive entry.** It was scored a miss on 79 cases, where
`hides_a_subgroup` was False at every tolerance. On the 672-case benchmark it
is True at every tolerance, with the worst band at 49.0% against a 20%
budget. The underpowered experiment reported no hidden subgroup; there was
one. That is what `src/abstain/power.py` exists to prevent.

**D1–D5 were withdrawn rather than scored.** Round three's design could not
test them: ~11 calibration cases per band against a Clopper–Pearson floor of
23.8%, and ~8 deployed cases per band against a question about a 10%
tolerance. Reporting them as failed would have been reporting noise.

**J1 is the one that cost the most.** It was the test of the strongest form of
the central claim, and the claim lost. The README states the narrowed version.

**All four L predictions missed, and together they found a mistake of
mine.** The concentration turns out to be *completely* insensitive to the
materiality threshold across two orders of magnitude — 4.07 at $0 against 4.11
at $500 — and then collapses to 1.55 when the award criterion is removed
entirely. That combination is only possible if `well-below`'s failures are
overwhelmingly award-driven, which contradicted a hypothesis I had tested and
rejected two rounds earlier.

The rejection had tested **all undetermined states** (31% award-only). The
rule commits on the **high-scoring** ones, and there it is **72%**. I walked
into the same selection effect that `calibrate_on_trajectories` exists to
handle. The corrected mechanism is in the README and the original reasoning is
kept, annotated, in `scripts/diagnose_mechanism.py`.

**Round O attacked the result that had refuted this repository's central
claim, lost three of five predictions, and found an error in the claim it was
defending.**

J1 refuted the strong form of the central claim: removing the distance feature
cut the concentration 4.13 → 1.72 and put every band inside the budget. That
had been reported prominently for two rounds without being attacked. Round O
attacked it, predicting the result was luck — the worst band moved only 12.48%
→ 11.65% as the budget fell by a quarter, which looks like a fixed failure
rate with the budget sliding past it.

**It is not.** At α = 0.10 the worst band falls to **3.79%**, coverage rises
to 97.79%, and nothing is hidden. The two-point extrapolation was the error,
not the hypothesis: at that tolerance the threshold is high enough that the
rule asks nearly everything, full information always resolves, and the rate
collapses. Two points either side of a regime change is not a trend — the C3
lesson again in a different shape.

**And the concern behind O1 was right on an estimator I had not thought to
name.** The same arm, at the same tolerance:

| | α = 0.20 | α = 0.15 | α = 0.10 |
|---|---:|---:|---:|
| worst band, pooled across 200 trials | 12.48% | 11.65% | **3.79%** |
| trials where **some** band exceeded α | 2.5% | **24.5%** | **26.0%** |

Both are honest numbers and they say different things, because one averages
over trials and the other counts failures. A quarter of deployments put a band
over budget while the across-trial rate sits comfortably inside it. **The
README said removing the feature "brings every band inside the budget", which
is true of the first row and false of a quarter of deployments** — the same
unit-of-aggregation error as the third bug and as the naive-versus-cluster
interval, found for the third time in this repository and the first time in a
claim that was mine rather than a metric's.

**O3 is the one with a consequence for practice.** At α = 0.10, group
conditioning on this scorer is feasible in **0 of 200 trials**, and 3 of 200
for the handcrafted one. So at that tolerance on 672 cases there is no remedy
available at all — not conditioning, and not a per-group certificate at any
price. Only a better-behaved score, whose per-group behaviour is then measured
rather than guaranteed.

The cost of tightening, with this scorer, is **questions**: 2.00 → 2.08 →
2.72 per case while coverage *rises* 92.75% → 97.79%. The repository frames
the trade as safety against coverage throughout; here it is safety against
interrogation, and that is the more useful framing when the question budget is
not the binding constraint.

**Round Q tested the partition the headline finding is phrased in, and the
finding survived.** Six of seven held. The one that matters is Q1: under
equal-count quartiles of income — cutoffs taken from the data's own
distribution with no reference to any result, 191/162/155/164 against the
hand-drawn 96/192/128/256 — the poorest quartile still runs at **27.3%
against a 20% budget** while the pooled rate is inside it. The subgroup
result is not an artefact of three constants in `scripts/split.py`.

Two things the round found that were **not** predicted, and both belong in the
record:

**A coarse partition hides it completely.** Two bands at the median report a
worst group of 15.8%, concentration 1.42, and `hides_a_subgroup` **False** at
both tolerances. An operator who checks for subgroup failure with two groups
concludes there is none. That is a stronger statement than Q6 asked for — Q6
predicted a low concentration, not that the finding would disappear — and it
is the most directly actionable thing in this round.

**Under the neutral partition the detection is tolerance-sensitive.** At
α = 0.20 the poorest quartile is 27.3% against 20% and the subgroup is
flagged. At α = 0.15 it is **14.54% against 15%** — inside the budget by 0.46
points, so `hides_a_subgroup` is False. The published partition flags it at
both. Reporting this as "the finding fails at 0.15" would overstate it as much
as omitting it would understate it: the quartile is twice as wide as
`well-below` and dilutes accordingly, and 0.46 points is not a margin anyone
should rely on in either direction.

**Q7 missed because of the partition I chose to test it with, not the claim.**
It predicted that eight bands would localise the effect further than four. The
eight-band split's lowest band is `income <= 6_000` — *identical to*
`well-below` — so it returned 4.1326 against 4.1326, the same number to every
digit. The claim itself is supported elsewhere in the same run: a 3,000 cutoff
gives 4.83. I should have noticed before running that the partition could not
possibly answer the question, and the run cost nothing extra, but a prediction
that cannot fail for the reason it was written is not a test.

**Rounds M and N are the worst two rounds in this ledger, and they produced
the sharpest single result in it.** Nine predictions, five missed, and the four
that held did so **vacuously** — they held because the thing being tested
changed nothing at all, so every cost prediction was satisfied by a no-op.
A round where the cost predictions pass for that reason is not a partial
success and the ledger should not let it read as one.

What happened: both rounds added a term to the scorer that fires only while
`dependents` is unknown, and the greedy question-selector asks for
`dependents` **first in every case that asks anything** — 447 of 447. So the
term acts on the opening state and nowhere else. An agent that does not commit
immediately asks the one question that switches the term off.

The result is that three scorers with **AUC 0.9425, 0.9555 and 0.9604**, which
reorder **3.0% and 4.8%** of the state pairs the rule can reach, produce
deployed behaviour identical **in every float**: same pooled rate, same four
band rates, same coverage, same questions per case, same group-conditional
figures, at both tolerances and under both schemes. Not identical to the
printed precision — identical under `==`, which
`tests/test_predictions.py` now checks.

> **A confidence function for a sequential agent cannot be evaluated on the
> state space. It has to be evaluated on the states the agent reaches under
> the rule.** AUC gave three different numbers for what is, in deployment,
> one policy — and it moved in *both directions* while nothing moved.

That is the fifth independent result in this repository about AUC failing to
see a threshold-local decision, and the strongest, because the other four
involved behaviour changing while AUC did not.

**M3 is where the scoring rule costs something.** It predicted the pooled rate
would come in "at or below the handcrafted scorer's 11.1%". It came in at
11.5% — and so did its own control, to every digit, because 11.1% was measured
in an earlier run at a different seed. Scored against its own control it holds;
scored against the number written down it misses, and that is how it is scored.
Either way its stated reason — "should improve the pooled figure, not merely
redistribute it" — is refuted, because it did neither.

**N1 held and was the wrong guard.** It was written to catch the failure mode
of round M by checking that the new term actually reorders states. It does, and
reordering was never what was broken. A pre-registered guard can be answered
correctly and still be aimed at the wrong thing; that is worth more than a
clean pass would have been.

**K1 and K2 missed in the method's favour, which is its own hazard.** I had
described the Clopper–Pearson correction as a finite-sample fix that should
dissolve once you have data, and predicted the plug-in would hold δ at 400
calibration cases. It does not, at any size tested — because the plug-in
targets a *point estimate* at α, and a point estimate at α is above α about
half the time. The failure was never about sample size. Being wrong produced
a better account of why the method works than being right would have, and a
prediction that misses in your favour is exactly the one it is tempting not
to score.
