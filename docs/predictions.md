# Every prediction, and what happened

Forty-eight predictions across six pre-registrations, each written before the
code that tested it. This table is the whole record: no prediction is omitted,
and the outcome column is the one that was true at the time, not the one that
would read best.

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

**K1 and K2 missed in the method's favour, which is its own hazard.** I had
described the Clopper–Pearson correction as a finite-sample fix that should
dissolve once you have data, and predicted the plug-in would hold δ at 400
calibration cases. It does not, at any size tested — because the plug-in
targets a *point estimate* at α, and a point estimate at α is above α about
half the time. The failure was never about sample size. Being wrong produced
a better account of why the method works than being right would have, and a
prediction that misses in your favour is exactly the one it is tempting not
to score.
