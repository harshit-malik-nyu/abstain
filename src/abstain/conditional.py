"""
Where does the error budget actually get spent?

The gap this measures
---------------------
Every number reported so far is marginal. One unsafe rate, pooled over all
deployed cases, checked against α. The conformal guarantee is marginal too —
it bounds the rate over the population and says nothing whatsoever about any
subgroup of it.

That matters here more than it would in most places. A 5% budget spent evenly
is five applicants in a hundred getting a decision built on a guess. The same
5% spent entirely on the hardest fifth of cases is a 25% failure rate for
those applicants, and the pooled figure reports 5% either way. The second
situation is much worse and the headline number cannot tell them apart.

This is not a defect specific to this method. Marginal-but-not-conditional
coverage is the standard caveat on split conformal procedures, and achieving
conditional coverage without distributional assumptions is known to be
impossible in general. So the question is not whether the guarantee is
conditional — it is not — but whether, on this benchmark, it happens to be
close enough that the marginal number is not misleading.

That is a measurement, and it has not been taken.

Why the strata are the split's strata
-------------------------------------
Income relative to the eligibility boundary, the four bands `split.py` already
uses. Reusing them rather than inventing a subgroup variable here is the point:
they were fixed in the first commit of the repository, before any method
existed, so there is no possibility that the subgroup was chosen after seeing
which breakdown made the method look better.

Both outcomes are reportable
----------------------------
The pre-registration says so in advance, and that is what makes this
experiment worth running. Concentrated budget → a limitation to name in the
README. Even budget → marginal and conditional coverage approximately coincide
*here*, which is reassuring about this benchmark and generalises to nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .evaluate import OPENING, ever_decidable

# Duplicated from `scripts/split.py` rather than imported.
#
# `split.py` is the first commit in this repository and its untouched state is
# the evidence that the split preceded the method. Editing it to export a
# helper would weaken that for a convenience. The duplication is instead
# pinned by `tests/test_conditional.py`, which asserts the two functions agree
# on every case in the benchmark — so a drift is a test failure rather than a
# silent disagreement between the split and the analysis of it.
BANDS = ("well-below", "near-threshold", "above", "well-above")


def hardness(case: dict) -> str:
    income = case["household"]["employment_income"]
    if income <= 6_000:
        return "well-below"
    if income <= 24_000:
        return "near-threshold"
    if income <= 36_000:
        return "above"
    return "well-above"


@dataclass
class StratumTally:
    band: str
    deployed: int = 0
    decidable: int = 0
    unsafe: int = 0
    resolved: int = 0
    abstained: int = 0

    @property
    def unsafe_rate(self) -> float:
        return self.unsafe / self.deployed if self.deployed else 0.0

    @property
    def coverage(self) -> float:
        return self.resolved / self.decidable if self.decidable else 0.0

    def as_dict(self) -> dict:
        return {"band": self.band, "deployed": self.deployed,
                "decidable": self.decidable, "unsafe": self.unsafe,
                "resolved": self.resolved, "abstained": self.abstained,
                "unsafe_rate": self.unsafe_rate, "coverage": self.coverage}


@dataclass
class Breakdown:
    """
    Pooled across trials, per stratum.

    Counts rather than averaged rates. A mean of per-trial rates weights a
    trial that deployed three cases of a band the same as one that deployed
    twelve, and with four bands over ~30 deployed cases some bands are empty
    in some trials. Summing the counts and dividing once is the estimator
    that does not need the bands to be balanced within a trial.
    """

    alpha: float
    tallies: dict[str, StratumTally] = field(default_factory=dict)
    trials: int = 0
    per_case: dict = field(default_factory=dict)
    """
    Per CASE, not per case-trial. The unit the uncertainty lives at.

    The band tallies above pool deployments across trials, and the same case
    appears in most of them — on the holdout, 96 distinct `well-below` cases
    produce 26,752 observations, about 279 each. A standard error computed
    from 26,752 would claim a precision of ±0.3 points on a figure whose real
    support is 96 cases.

    So each case's own deployment and unsafe counts are kept here, and
    `bootstrap_band_rate` resamples **cases** rather than observations. Which
    is the whole point: the naive interval is not merely optimistic, it is
    answering a question nobody asked — how precisely do we know the rate
    *for these 96 households*, rather than for households like them.
    """

    def tally(self, band: str) -> StratumTally:
        if band not in self.tallies:
            self.tallies[band] = StratumTally(band=band)
        return self.tallies[band]

    @property
    def pooled_unsafe_rate(self) -> float:
        d = sum(t.deployed for t in self.tallies.values())
        u = sum(t.unsafe for t in self.tallies.values())
        return u / d if d else 0.0

    @property
    def worst_band(self) -> str | None:
        """The band with the highest unsafe rate, among those ever deployed."""
        seen = [t for t in self.tallies.values() if t.deployed]
        if not seen:
            return None
        return max(seen, key=lambda t: t.unsafe_rate).band

    @property
    def hides_a_subgroup(self) -> bool:
        """
        True when the pooled rate is within budget and some band is not.

        The prediction under test. If this is true, the headline guarantee is
        being honoured on average while a identifiable group of applicants is
        over budget, and saying "the rule holds α" without qualification would
        be true and misleading at once.
        """
        if self.pooled_unsafe_rate > self.alpha:
            return False
        return any(t.unsafe_rate > self.alpha
                   for t in self.tallies.values() if t.deployed)

    @property
    def concentration(self) -> dict[str, float]:
        """
        Each band's share of unsafe commitments over its share of deployments.

        1.0 means the band absorbs exactly its proportional part of the
        budget. Above 1.0 means it absorbs more. Expressed as a ratio rather
        than two percentages because the quantity of interest is the
        disproportion, and a ratio is the thing that is comparable across
        bands of different size.
        """
        total_d = sum(t.deployed for t in self.tallies.values())
        total_u = sum(t.unsafe for t in self.tallies.values())
        out = {}
        for band, t in self.tallies.items():
            if not t.deployed or not total_u or not total_d:
                out[band] = 0.0
                continue
            share_u = t.unsafe / total_u
            share_d = t.deployed / total_d
            out[band] = share_u / share_d if share_d else 0.0
        return out

    def as_dict(self) -> dict:
        return {
            "alpha": self.alpha,
            "trials": self.trials,
            "pooled_unsafe_rate": self.pooled_unsafe_rate,
            "worst_band": self.worst_band,
            "hides_a_subgroup": self.hides_a_subgroup,
            "concentration": self.concentration,
            "bands": [self.tallies[b].as_dict() for b in BANDS
                      if b in self.tallies],
        }


def collector(breakdown: Breakdown):
    """
    An `on_trial` callback that accumulates the per-stratum tally.

    Reads the per-case detail `evaluate` already records, so the breakdown is
    computed from the same trajectories the headline number is computed from —
    not from a second run that could differ. The outcome labels are
    `evaluate`'s own, which keeps the definition of "unsafe" in exactly one
    place.
    """
    def on_trial(cal, result, dep_cases):
        breakdown.trials += 1
        by_id = {c.get("id"): c for c in dep_cases}

        for row in result.detail:
            case = by_id.get(row["case"])
            if case is None:
                continue
            outcome = row["outcome"]
            band = hardness(case)
            t = breakdown.tally(band)
            t.deployed += 1

            cid = row["case"]
            rec = breakdown.per_case.setdefault(
                cid, {"band": band, "deployed": 0, "unsafe": 0})
            rec["deployed"] += 1
            if outcome == "unsafe":
                rec["unsafe"] += 1
            if ever_decidable(case):
                t.decidable += 1
            if outcome == "unsafe":
                t.unsafe += 1
            elif outcome == "abstained":
                t.abstained += 1
            else:
                t.resolved += 1

    return on_trial


def population_shares(cases: list[dict]) -> dict[str, float]:
    """
    Each band's share of the case pool.

    Context for `concentration`: a band holding 40% of the cases and 40% of
    the unsafe commitments is not a finding, and the ratio already says so,
    but the reader wants the denominator in front of them.
    """
    counts: dict[str, int] = {}
    for c in cases:
        b = hardness(c)
        counts[b] = counts.get(b, 0) + 1
    return {b: counts.get(b, 0) / len(cases) for b in BANDS} if cases else {}


def undetermined_share(cases: list[dict]) -> dict[str, float]:
    """
    Per band, the share of reachable knowledge states that are undecidable.

    The mechanism behind whatever `concentration` shows. If `near-threshold`
    absorbs the budget, this is the reason: near the boundary the unknown
    fields move the verdict, so more states are open and committing early is
    more often wrong. Reporting the mechanism alongside the effect is what
    separates an explanation from a correlation.

    Counts the opening state too, since that is where the rule starts and a
    rule that commits immediately commits there.
    """
    tot: dict[str, list[int]] = {b: [0, 0] for b in BANDS}
    for c in cases:
        b = hardness(c)
        for key, state in c["states"].items():
            if "employment_income" not in key.split("|"):
                # Unreachable: the opening state always knows income, and the
                # rule only ever adds fields. Including states the rule cannot
                # be in would dilute the number with irrelevant ones.
                continue
            tot[b][1] += 1
            if state["label"] == "underdetermined":
                tot[b][0] += 1
    return {b: (n / d if d else 0.0) for b, (n, d) in tot.items()}


assert OPENING == frozenset({"employment_income"}), (
    "undetermined_share filters reachable states by assuming the opening "
    "state knows income; if OPENING changes, that filter is wrong"
)


# ---------------------------------------------------------------------------
# Uncertainty, at the unit the data actually has
# ---------------------------------------------------------------------------

def bootstrap_band_rate(per_case: dict, band: str, *, draws: int = 5_000,
                        seed: int = 97,
                        level: float = 0.95) -> dict:
    """
    A confidence interval for a band's unsafe rate, resampling **cases**.

    Why not a binomial interval on the pooled count
    -----------------------------------------------
    Because the pooled count is not a sample of independent observations. On
    the holdout, 96 distinct `well-below` cases are deployed about 279 times
    each, and a Clopper–Pearson interval on 13,097 unsafe out of 26,752 comes
    out about ±0.6 points. That number is not conservative or optimistic; it
    answers a different question — how precisely the rate is known *for these
    96 households* — when the claim being made is about households like them.

    The cluster is the case. Each case contributes its own deployment and
    unsafe counts across however many trials it appeared in, and the
    resampling draws cases with replacement. The interval then reflects the
    96 units of real variation rather than the 26,752 repeats of them.

    This is an ordinary cluster bootstrap and nothing here is novel. What
    would have been novel is reporting the naive interval.
    """
    import random as _random

    rows = [v for v in per_case.values() if v["band"] == band]
    if not rows:
        return {"band": band, "cases": 0, "point": 0.0,
                "lo": 0.0, "hi": 0.0, "naive_halfwidth": 0.0}

    deployed = sum(r["deployed"] for r in rows)
    unsafe = sum(r["unsafe"] for r in rows)
    point = unsafe / deployed if deployed else 0.0

    rng = _random.Random(seed)
    n = len(rows)
    rates = []
    for _ in range(draws):
        d = u = 0
        for _ in range(n):
            r = rows[rng.randrange(n)]
            d += r["deployed"]
            u += r["unsafe"]
        rates.append(u / d if d else 0.0)
    rates.sort()

    tail = (1.0 - level) / 2.0
    lo = rates[int(tail * (draws - 1))]
    hi = rates[int((1.0 - tail) * (draws - 1))]

    # What a reader would have got by treating every observation as
    # independent — reported alongside so the difference is visible rather
    # than asserted.
    from .rule import clopper_pearson_upper
    naive_hi = clopper_pearson_upper(unsafe, deployed, (1.0 - level) / 2.0) \
        if deployed else 1.0

    return {"band": band, "cases": n, "observations": deployed,
            "point": point, "lo": lo, "hi": hi, "level": level,
            "naive_halfwidth": max(0.0, naive_hi - point),
            "clustered_halfwidth": max(point - lo, hi - point)}


def bootstrap_all_bands(per_case: dict, **kw) -> list[dict]:
    present = [b for b in BANDS
               if any(v["band"] == b for v in per_case.values())]
    return [bootstrap_band_rate(per_case, b, **kw) for b in present]
