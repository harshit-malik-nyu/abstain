"""
Properties of the benchmark that every result in this repository assumes.

Why this file exists
--------------------
Everything else in this suite tests the *method*, or checks that the write-up
reports what the runs produced. Nothing tested the **data**, and the data is
where the deepest threat to the headline result lives: the subgroup finding is
a statement about a label — `determinable` — that comes from PolicyEngine, and
if that label were internally inconsistent in a way correlated with income,
the finding would be an artefact of the oracle rather than a property of the
rule.

That cannot be settled without a second oracle. What *can* be settled is
whether the labels are internally coherent, and these four invariants are the
ones every argument in the repository silently relies on:

1. **Monotonicity.** Knowing more cannot un-settle a verdict. If a state is
   `determinable`, every state reachable by learning one more field must be
   too. Otherwise "undetermined" does not mean "not enough information yet"
   and the whole framing is wrong.
2. **Verdict stability.** A settled verdict cannot change as more is learned.
   If it could, "determinable" would not mean the answer is fixed.
3. **Full information is determinable.** With every field known the oracle
   must reach a verdict, or the benchmark contains cases no amount of asking
   resolves — which would make the abstention rate a property of the data
   rather than of the budget.
4. **The group is observable at decision time.** `hardness` must depend only
   on fields the agent knows at the opening state. Mondrian conformal
   prediction calibrates per group and the agent has to know which group it is
   in *when it decides*; a band that depended on an unknown field would make
   group conditioning invalid while every number in the repository still
   looked fine.

All four hold, on all four benchmarks. Nothing checked them until now, which
is exactly why they are worth checking: an assumption that holds and is never
stated is one edit away from an assumption that does not hold and is never
noticed.

A note on the holdout, and a carve-out I did not take
-----------------------------------------------------
The first version of this file checked all four benchmarks, holdouts
included, and `test_preregistration.py` failed it — the guard that whitelists
which files may read a holdout does not whitelist this one.

The argument for an exception was easy to make and I had already written it
down: a structural invariant decides nothing about the method and measures no
performance on it, so reading a holdout to check that its labels are coherent
spends none of it. That is probably true. It is also exactly the shape of
reasonable-sounding carve-out that turns a holdout guard into a formality, and
the whitelist's value comes from a reader being able to see at a glance which
code ever touched those files.

So the sets below are the development halves only. 751 cases and roughly
5,500 label pairs are ample for an internal-consistency check, and if a
holdout half were ever inconsistent it would show when that half was opened —
by the script that is allowed to open it.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

FIELDS = ("age", "dependents", "employment_income", "state_name")
FULL = "|".join(sorted(FIELDS))

# The development halves only — see the note above on the carve-out this file
# does not take. `dev` is the 79-case original, `fine_dev` the 672-case
# benchmark every current result uses.
SETS = ("dev.json", "fine_dev.json")


def load(name: str) -> list[dict]:
    p = ROOT / "evidence" / name
    if not p.exists():
        pytest.skip(f"{name} not present in this checkout")
    return json.loads(p.read_text())


def known_of(key: str) -> frozenset[str]:
    """The opening state is the empty key, not a field named ''."""
    return frozenset(key.split("|")) - {""}


@pytest.mark.parametrize("name", SETS)
def test_determinability_is_monotone_in_what_is_known(name):
    """
    Invariant 1. Learning one more field cannot make a settled case unsettled.

    Checked over every (state, one-field-larger state) pair rather than only
    the ones the rule visits, because the calibration population is the full
    state space and a violation anywhere would mean the label does not mean
    what the write-up says it means.
    """
    cases = load(name)
    checked = 0
    bad = []
    for c in cases:
        st = c["states"]
        for key, s in st.items():
            if s["label"] != "determinable":
                continue
            k1 = known_of(key)
            for other, s2 in st.items():
                k2 = known_of(other)
                if len(k2) == len(k1) + 1 and k1 < k2:
                    checked += 1
                    if s2["label"] != "determinable":
                        bad.append((c.get("id"), key, other, s2["label"]))
    assert checked > 200, (name, checked)
    assert not bad, bad[:5]


@pytest.mark.parametrize("name", SETS)
def test_a_settled_verdict_never_changes(name):
    """
    Invariant 2. Two determinable states of the same case, one knowing more
    than the other, must agree on the verdict.

    Stronger than monotonicity and a different failure: monotonicity could
    hold while the answer flipped from eligible to ineligible as fields
    arrived, which would make "determinable" mean "the oracle committed",
    not "the answer is fixed".
    """
    cases = load(name)
    checked = 0
    bad = []
    for c in cases:
        st = c["states"]
        det = [(known_of(k), s) for k, s in st.items()
               if s["label"] == "determinable"]
        for k1, s1 in det:
            for k2, s2 in det:
                if k1 < k2:
                    checked += 1
                    if s1.get("truth") != s2.get("truth"):
                        bad.append((c.get("id"), sorted(k1), s1.get("truth"),
                                    sorted(k2), s2.get("truth")))
    assert checked > 200, (name, checked)
    assert not bad, bad[:5]


@pytest.mark.parametrize("name", SETS)
def test_full_information_always_resolves(name):
    """
    Invariant 3. Every case is answerable once everything is known.

    If it were not, some abstentions would be forced by the data rather than
    by the budget, and `coverage` would be bounded above by something the
    write-up never mentions.
    """
    cases = load(name)
    missing = [c.get("id") for c in cases if FULL not in c["states"]]
    assert not missing, missing[:5]

    unresolved = [c.get("id") for c in cases
                  if c["states"][FULL]["label"] != "determinable"]
    assert not unresolved, unresolved[:5]

    no_truth = [c.get("id") for c in cases
                if not c["states"][FULL].get("truth")]
    assert not no_truth, no_truth[:5]


def test_the_group_is_observable_when_the_agent_decides():
    """
    Invariant 4, and the one with teeth: `hardness` must read only fields the
    agent already knows at the opening state.

    Mondrian conformal prediction gives each group its own threshold, and the
    agent has to know which group it is in at the moment it decides. If
    `hardness` were changed to read `dependents`, group conditioning would
    become invalid — the rule would be selecting a threshold using a value it
    has not been told — and nothing else in this suite would fail, because
    every experiment computes the band from the full case record.

    Asserted against the source rather than against behaviour, because the
    failure is a field being *read*, not a number coming out wrong.
    """
    from abstain.conditional import hardness
    from abstain.evaluate import OPENING

    src = inspect.getsource(hardness)
    read = {f for f in FIELDS if f in src}
    assert read, "hardness reads no household field at all; check this test"
    assert read <= set(OPENING), (
        f"hardness reads {sorted(read - set(OPENING))}, which the agent does "
        f"not know at the opening state — group conditioning on it would use "
        f"information the rule has not been given")


def test_every_band_is_populated_in_every_benchmark():
    """
    A band with no cases would make its per-group rate undefined, and the
    concentration ratio it feeds divides by its share of cases.

    Not a deep property — a guard against a benchmark rebuild that silently
    empties a stratum, which would turn `concentration` into a division by
    zero reported as 0.0.
    """
    from abstain.conditional import BANDS, hardness

    for name in SETS:
        cases = load(name)
        counts = {b: 0 for b in BANDS}
        for c in cases:
            counts[hardness(c)] += 1
        empty = [b for b, n in counts.items() if n == 0]
        assert not empty, (name, counts)


def test_the_opening_state_knows_income_and_nothing_else():
    """
    Three separate arguments rest on this exact set, so it is pinned once
    here rather than assumed in three places: the reachable-state filter in
    `conditional.undetermined_share`, the band being observable above, and
    the claim that the selector's first question is the agent's first
    real choice.
    """
    from abstain.evaluate import OPENING
    assert OPENING == frozenset({"employment_income"}), OPENING
