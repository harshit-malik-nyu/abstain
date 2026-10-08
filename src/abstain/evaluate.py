"""
Run the rule and the reference policies over a set of cases.

What is being compared
----------------------
Not accuracy. The benchmark's three failure modes are unequal and a policy can
be perfect on any one of them by refusing to do anything:

    unsafe     answered while the case was still underdetermined
    coverage   share of decidable cases actually resolved
    questions  what the applicant was asked for

Reporting one without the others recommends a degenerate policy, which is why
every summary here carries all three.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .rule import run_case

OPENING = frozenset({"employment_income"})


@dataclass
class Result:
    name: str
    n: int = 0
    unsafe: int = 0
    resolved_right: int = 0
    resolved_wrong: int = 0
    abstained: int = 0
    questions: int = 0
    decidable: int = 0
    detail: list[dict] = field(default_factory=list)

    @property
    def unsafe_rate(self) -> float:
        return self.unsafe / self.n if self.n else 0.0

    @property
    def coverage(self) -> float:
        """Of the cases that were ever decidable, how many were resolved?"""
        return ((self.resolved_right + self.resolved_wrong) / self.decidable
                if self.decidable else 0.0)

    @property
    def questions_per_case(self) -> float:
        return self.questions / self.n if self.n else 0.0

    @property
    def accuracy(self) -> float:
        tot = self.resolved_right + self.resolved_wrong
        return self.resolved_right / tot if tot else 0.0

    def as_dict(self) -> dict:
        return {"policy": self.name, "n": self.n,
                "unsafe_rate": self.unsafe_rate,
                "coverage": self.coverage,
                "questions_per_case": self.questions_per_case,
                "accuracy_when_resolved": self.accuracy,
                "abstained": self.abstained,
                "decidable_cases": self.decidable}


def ever_decidable(case: dict) -> bool:
    """Could any reachable knowledge state have been answered?"""
    return any(s["label"] == "determinable" for s in case["states"].values())


def final_truth(case: dict, known: frozenset[str]) -> str:
    return case["states"]["|".join(sorted(known))]["truth"]


def evaluate(cases: list[dict], scorer, threshold: float, name: str,
             budget: int = 4) -> Result:
    r = Result(name=name, n=len(cases))
    for case in cases:
        if ever_decidable(case):
            r.decidable += 1
        t = run_case(case, scorer, threshold, budget=budget, opening=OPENING)
        r.questions += t.questions

        known = set(OPENING) | set(t.asked)
        truth = final_truth(case, frozenset(known))

        # Whether the rule COMMITTED is what matters, not what verdict came
        # out. An agent that chose to answer an undecidable case has guessed
        # whichever way it guessed.
        if not t.committed:
            r.abstained += 1
            outcome = "abstained"
        elif truth == "cannot_determine":
            r.unsafe += 1
            outcome = "unsafe"
        elif t.final == truth:
            r.resolved_right += 1
            outcome = "correct"
        else:
            r.resolved_wrong += 1
            outcome = "wrong"

        r.detail.append({"case": case.get("id"), "asked": t.asked,
                         "final": t.final, "truth": truth,
                         "outcome": outcome, "scores": t.scores})
    return r


# ---------------------------------------------------------------------------
# Reference policies, as scorer/threshold pairs
# ---------------------------------------------------------------------------

def answer_immediately(cases: list[dict], budget: int = 4) -> Result:
    """Threshold zero: the score always clears, so it never asks."""
    return evaluate(cases, lambda c, k: 1.0, 0.0, "answer immediately", budget)


def ask_everything(cases: list[dict], budget: int = 4) -> Result:
    """
    Threshold above one: the score never clears, so it asks until the budget
    is gone and then abstains. Safe and resolves nothing, which is the point
    of including it.
    """
    return evaluate(cases, lambda c, k: 0.0, 1.1, "ask everything", budget)


def oracle(cases: list[dict], budget: int = 4) -> Result:
    """
    The ceiling: answers exactly when the current state is decidable.

    Not implementable — it reads the verdict it is supposed to predict. It
    exists to say what perfect information-seeking costs in questions, which
    is the number a method should be compared against rather than zero.
    """
    def sc(case, known):
        return 1.0 if case["states"]["|".join(sorted(known))]["label"] == \
            "determinable" else 0.0
    return evaluate(cases, sc, 0.5, "oracle (ceiling)", budget)
