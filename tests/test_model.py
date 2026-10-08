"""
The model-backed scorer, against a scripted transport.

What these establish, and what they cannot
------------------------------------------
They check the protocol: that the prompt carries what the model needs to
answer the question the benchmark scores against, that replies in the shapes
models actually produce are parsed, that a failed reply is recorded rather
than silently defaulted, and — the one that matters most — that the scorer is
a **function**, not a sampler.

They establish nothing about whether a model's confidence is any good. No
number in this repository comes from a model, and `tests/` cannot change that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from abstain.model import (ModelScorer, SWEEPABLE_TEXT, build_prompt, parse)
from abstain.scorer import FIELDS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def case():
    return {"id": 7,
            "household": {"employment_income": 18_000, "dependents": 2,
                          "age": 35, "state_name": "NY"},
            "states": {}}


def scripted(*replies: str):
    """A transport that returns its replies in order, then repeats the last."""
    seen = []

    def send(prompt: str) -> str:
        seen.append(prompt)
        return replies[min(len(seen) - 1, len(replies) - 1)]

    send.prompts = seen  # type: ignore[attr-defined]
    return send


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------

def test_the_prompt_separates_what_is_known_from_what_is_not(case):
    text = build_prompt(case, frozenset({"employment_income", "age"}))
    assert "employment income: 18000" in text
    assert "age: 35" in text
    # The unknown ones appear with their ranges, not their values.
    assert "2" not in text.split("do not know")[1].split("Question")[0] or \
        "dependents: 0 to 3" in text
    assert "dependents: 0 to 3" in text
    assert "state name: NY, TX, CA or MS" in text


def test_the_prompt_never_leaks_an_unknown_value(case):
    """
    The agent may not see a field it has not been told, and a prompt bug is
    the easiest way for that to happen without anything failing.
    """
    text = build_prompt(case, frozenset({"employment_income"}))
    block = text.split("do not know")[1]
    assert "35" not in block, "the age leaked into the unknown block"
    assert "NY," in block or "NY " in block  # as a range member, not a value
    assert ": NY\n" not in text.split("Question")[0].split("do not know")[1]


def test_the_prompt_quotes_the_ranges_the_oracle_sweeps(case):
    """
    Without the ranges, "could this change the answer" is a question about a
    support the model has to guess, and its answer is then about a different
    question than the benchmark scores.
    """
    text = build_prompt(case, frozenset())
    for name in FIELDS:
        assert SWEEPABLE_TEXT[name] in text, name


def test_the_prompt_asks_for_a_number_in_a_named_field(case):
    text = build_prompt(case, frozenset({"employment_income"}))
    assert '"determinable"' in text
    assert "0 and 1" in text or "0 to 1" in text
    assert "nothing else" in text, "a free-form reply is harder to parse"


def test_every_state_produces_a_well_formed_prompt(case):
    import itertools
    for r in range(len(FIELDS) + 1):
        for known in itertools.combinations(FIELDS, r):
            text = build_prompt(case, frozenset(known))
            assert "determinable" in text
            assert "{" not in text.replace('{"determinable"', ""), \
                f"unfilled template placeholder at {known}"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_it_reads_a_clean_json_reply():
    assert parse('{"determinable": 0.8, "why": "income decides it"}') == 0.8


def test_it_reads_a_fenced_or_chatty_reply():
    """
    Models produce all three shapes, and a parser that accepts only the first
    turns a formatting difference into missing data.
    """
    assert parse('```json\n{"determinable": 0.25}\n```') == 0.25
    assert parse('Here you go: {"determinable": 0.6, "why": "x"}') == 0.6
    assert parse('I think {"determinable": 0.0} is right.') == 0.0


def test_it_clamps_out_of_range_values():
    assert parse('{"determinable": 1.7}') == 1.0
    assert parse('{"determinable": -0.2}') == 0.0


def test_an_unreadable_reply_is_none_not_a_default():
    """
    A malformed reply scored 0.5 would enter calibration as a real
    observation, and the bound would then be computed over a mixture of
    measurements and failures.
    """
    assert parse("I'm not sure.") is None
    assert parse("") is None
    assert parse('{"confidence": 0.5}') is None


# ---------------------------------------------------------------------------
# The scorer is a function
# ---------------------------------------------------------------------------

def test_the_same_state_is_scored_once_however_often_it_is_asked(case):
    """
    The requirement the whole design turns on.

    The rule evaluates a state more than once — the question selector looks
    ahead at each candidate field, then the stopping rule scores where it
    landed — and the conformal argument needs the score fixed. A scorer that
    called the API each time would return a different number for the same
    state, and a violation would then be attributable to the non-determinism
    rather than to the score.
    """
    transport = scripted('{"determinable": 0.4}', '{"determinable": 0.9}')
    s = ModelScorer(transport=transport)
    known = frozenset({"employment_income"})

    first = s(case, known)
    assert all(s(case, known) == first for _ in range(5))
    assert s.calls == 1, "the transport was called more than once"


def test_different_states_are_scored_separately(case):
    s = ModelScorer(transport=scripted('{"determinable": 0.4}',
                                       '{"determinable": 0.9}'))
    a = s(case, frozenset({"employment_income"}))
    b = s(case, frozenset({"employment_income", "age"}))
    assert (a, b) == (0.4, 0.9)
    assert s.calls == 2


def test_an_unparseable_reply_is_cautious_and_counted(case):
    """
    0.0, not a middling value: a reply the harness cannot read is not
    evidence that the case is safe to answer.
    """
    s = ModelScorer(transport=scripted("sorry, I can't"))
    assert s(case, frozenset({"age"})) == 0.0
    assert s.unparseable == 1
    assert s.unparseable_rate == 1.0


def test_failures_are_scored_rather_than_dropped(case):
    """
    Dropping them would condition the calibration set on the model having
    replied well — a selection effect on exactly the states it struggled
    with.
    """
    s = ModelScorer(transport=scripted("nope"))
    s(case, frozenset({"age"}))
    assert len(s.cache) == 1, "the failed state must still be in the cache"


def test_the_cache_round_trips(tmp_path, case):
    path = tmp_path / "cache.json"
    first = ModelScorer(transport=scripted('{"determinable": 0.33}'),
                        cache_path=path)
    first(case, frozenset({"employment_income"}))
    first.save()

    second = ModelScorer(transport=scripted('{"determinable": 0.99}'),
                         cache_path=path)
    assert second(case, frozenset({"employment_income"})) == 0.33
    assert second.calls == 0, "a cached state must not reach the transport"


def test_it_satisfies_the_scorer_contract(case):
    """
    Same `(case, known) -> float` signature as every other scorer here, so it
    drops into the rule unchanged. That is the point of the contract being
    this small.
    """
    from abstain.rule import run_case

    full = {"|".join(sorted(k)): {"label": "determinable", "truth": "eligible"}
            for k in [(), ("employment_income",),
                      ("age", "employment_income")]}
    import itertools
    for r in range(len(FIELDS) + 1):
        for known in itertools.combinations(FIELDS, r):
            full.setdefault("|".join(sorted(known)),
                            {"label": "underdetermined",
                             "truth": "cannot_determine"})
    case = dict(case, states=full)

    s = ModelScorer(transport=scripted('{"determinable": 0.95}'))
    t = run_case(case, s, threshold=0.5)
    assert t.committed
    assert isinstance(s(case, frozenset()), float)


# ---------------------------------------------------------------------------
# The honesty of the module
# ---------------------------------------------------------------------------

def test_the_module_says_it_has_not_been_run():
    """
    It would be easy for this to read as a result. It is not one.
    """
    import abstain.model as m
    # Whitespace-normalised: the claim is wrapped across lines in the source
    # and a raw substring check would pass or fail on where the wrap lands.
    doc = " ".join((m.__doc__ or "").split())
    assert "has not been run against a real model" in doc.lower()
    assert "No number in this repository comes from it" in doc


def test_no_evidence_file_claims_a_model_run():
    """
    If a model is ever run, this fails and forces the claim to be made
    explicitly rather than appearing in a table.
    """
    for path in (ROOT / "evidence").glob("*.json"):
        try:
            blob = json.dumps(json.loads(path.read_text()))[:200_000]
        except Exception:
            continue
        assert "ModelScorer" not in blob, path.name
