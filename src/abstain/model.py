"""
A scorer backed by a language model, and the one thing it must not get wrong.

Why this exists unrun
---------------------
`docs/against.md` leads with the objection that cannot be fully answered here:
no language model was run. The rule is evaluated against an oracle-backed
simulation where determinability is computable, and the deployment it is
motivated by is one where it is not.

The corruption study in `robustness.py` brackets the answer — a conformal
abstention wrapper on a badly-ordered confidence signal stays safe and becomes
nearly useless — and a bracket is not a measurement. What is missing is a key,
not a design.

So the design is here, tested against a scripted transport, with the gap
stated rather than papered over. It turns "someone should try this" into one
command and a key, and it makes the prompt a reviewable artefact instead of a
footnote: what you ask a model for determines what its confidence is worth,
and that choice belongs in the repository.

**This has not been run against a real model.** No number in this repository
comes from it. `tests/test_model.py` exercises the protocol with a
scripted transport, which checks that the plumbing is right and says nothing
about whether a model's confidence is any good.

The requirement that is easy to get wrong
-----------------------------------------
**The score must be a function.** The rule evaluates the same knowledge state
more than once — the question selector looks ahead at each candidate field,
and then the stopping rule scores the state it lands on — and the conformal
argument needs the score fixed with respect to the calibration and deployment
data. A scorer that calls the API afresh each time returns a different number
for the same state, and then a violation is attributable to the
non-determinism rather than to the score.

This is not a hypothetical: `robustness.noisy` hit exactly this and had to be
made deterministic, and the first version of it seeded from `hash()`, which
Python salts per process, so it was a different function in every run.

So every call is cached on the state, and the cache is the mechanism that
makes the scorer a function rather than a sampler. Temperature is pinned to 0
as well, but that is a weaker guarantee than the cache: providers do not
promise determinism at temperature 0, and a cache does not need them to.

What a run would cost
---------------------
The benchmark is 1,344 cases × 16 knowledge states, but the rule only visits
states reachable from the opening, and caches across cases that share a
field combination. A full calibration-and-deployment pass over the 672-case
dev half touches on the order of a few thousand distinct states. Budget
accordingly, and note that `cache_path` makes a re-run free.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

from .scorer import FIELDS

# The ranges the oracle sweeps, quoted to the model so that "could this change
# the answer" is a question about the same space the benchmark scores against.
# Asking without them makes the model guess at the support, and its answer is
# then about a different question than the one being measured.
SWEEPABLE_TEXT = {
    "employment_income": "$0 to $60,000",
    "dependents": "0 to 3",
    "age": "22 to 64",
    "state_name": "NY, TX, CA or MS",
}

PROMPT = """\
You are screening an application for SNAP (food assistance) in the United \
States for calendar year {year}.

What you know about this household:
{known}

What you do not know, and the range each could take:
{unknown}

Question: if you had to decide eligibility **right now**, could the unknown \
fields change the answer?

Answer with a JSON object and nothing else:

  {{"determinable": <number between 0 and 1>, "why": "<one short clause>"}}

`determinable` is your confidence that the eligibility verdict is already \
settled by what you know — that no combination of the unknown fields, within \
the ranges above, would change it. Use the full range: 0.0 means the unknown \
fields clearly decide it, 1.0 means they clearly cannot.\
"""


class Transport(Protocol):
    """
    Anything that turns a prompt into text.

    Deliberately this small. The repository has no runtime dependency beyond
    the standard library, and taking one for an experiment that has not been
    run would be the wrong trade — a caller wires in their own client in four
    lines.
    """

    def __call__(self, prompt: str) -> str: ...


def describe(case: dict, known: frozenset[str], year: int = 2025
             ) -> tuple[str, str]:
    """The known and unknown blocks of the prompt, as text."""
    hh = case["household"]
    known_lines, unknown_lines = [], []
    for name in FIELDS:
        label = name.replace("_", " ")
        if name in known:
            known_lines.append(f"  - {label}: {hh[name]}")
        else:
            unknown_lines.append(f"  - {label}: {SWEEPABLE_TEXT[name]}")
    return ("\n".join(known_lines) or "  (nothing)",
            "\n".join(unknown_lines) or "  (nothing)")


def build_prompt(case: dict, known: frozenset[str], year: int = 2025) -> str:
    k, u = describe(case, known, year)
    return PROMPT.format(year=year, known=k, unknown=u)


_NUMBER = re.compile(r'"determinable"\s*:\s*([0-9]*\.?[0-9]+)')


def parse(text: str) -> float | None:
    """
    Pull the confidence out of a reply, or report that there wasn't one.

    `None` rather than a default, and that distinction matters more than it
    looks. A malformed reply silently scored 0.5 would enter calibration as a
    real observation and the bound would be computed over a mixture of
    measurements and failures. The caller decides what an unparseable reply
    means; this does not decide for them.

    Tolerates a JSON object, a fenced block, or prose with the field embedded,
    because models produce all three and a parser that only accepts the first
    turns a formatting difference into missing data.
    """
    text = text.strip()
    try:
        value = json.loads(text)["determinable"]
        return min(1.0, max(0.0, float(value)))
    except Exception:
        pass

    m = _NUMBER.search(text)
    if not m:
        return None
    try:
        return min(1.0, max(0.0, float(m.group(1))))
    except ValueError:
        return None


@dataclass
class ModelScorer:
    """
    A `Scorer` whose ordering comes from a language model.

    Satisfies the same `(case, known) -> float` contract as every other scorer
    here, so it drops into `calibrate_on_trajectories`, `validate` and
    `validate_groups` unchanged. That is the point of the contract being that
    small.
    """

    transport: Transport
    on_unparseable: float = 0.0
    """
    What an unreadable reply scores.

    0.0 — the most cautious value — rather than a middling one, because a
    reply the harness cannot read is not evidence that the case is safe to
    answer, and a scorer is allowed to be pessimistic. It is **not** dropped:
    dropping failures would quietly condition the calibration set on the model
    having replied well, which is a selection effect on exactly the states
    where it struggled.
    """

    cache: dict[tuple, float] = field(default_factory=dict)
    cache_path: Path | None = None
    calls: int = 0
    unparseable: int = 0

    def __post_init__(self) -> None:
        if self.cache_path and Path(self.cache_path).exists():
            raw = json.loads(Path(self.cache_path).read_text())
            # JSON has no tuples, so the known-field set comes back as a list
            # and the restored key is unhashable. Rebuilding it explicitly
            # rather than with a bare `tuple(...)`, which only fixes the outer
            # level and raises on the first lookup.
            self.cache = {}
            for serialised, value in raw.items():
                case_id, known = json.loads(serialised)
                self.cache[(case_id, tuple(known))] = value

    def key(self, case: dict, known: frozenset[str]) -> tuple:
        return (case.get("id", -1), tuple(sorted(known)))

    def __call__(self, case: dict, known: frozenset[str]) -> float:
        k = self.key(case, known)
        if k in self.cache:
            return self.cache[k]

        self.calls += 1
        value = parse(self.transport(build_prompt(case, known)))
        if value is None:
            self.unparseable += 1
            value = self.on_unparseable

        self.cache[k] = value
        return value

    def save(self) -> None:
        if not self.cache_path:
            return
        Path(self.cache_path).write_text(json.dumps(
            {json.dumps(list(k)): v for k, v in self.cache.items()},
            indent=1, sort_keys=True))

    @property
    def unparseable_rate(self) -> float:
        return self.unparseable / self.calls if self.calls else 0.0

    def as_dict(self) -> dict:
        return {"states_scored": len(self.cache), "api_calls": self.calls,
                "unparseable": self.unparseable,
                "unparseable_rate": self.unparseable_rate}


def anthropic_transport(model: str, api_key: str,
                        max_tokens: int = 128) -> Callable[[str], str]:
    """
    A transport for Anthropic's API, written out rather than imported.

    The `anthropic` package is not a dependency of this repository and should
    not become one for an experiment nobody has run. This builds the request
    with the standard library, so a reader can see exactly what is sent —
    including `temperature=0`, which is a weaker determinism guarantee than
    the cache and is set anyway.

    **Untested against the live API.** `tests/test_model.py` exercises
    everything above this function with a scripted transport; this function
    is the one part that cannot be tested without a key, and it is kept to
    the smallest possible surface for that reason.
    """
    import urllib.request

    def send(prompt: str) -> str:
        body = json.dumps({
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=body,
            headers={"content-type": "application/json",
                     "anthropic-version": "2023-06-01",
                     "x-api-key": api_key})
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.loads(r.read())
        return "".join(block.get("text", "")
                       for block in payload.get("content", []))

    return send
