"""
abstain — a selection rule that bounds how often an agent answers blind.

The operator names a tolerance and gets it:

    give me an unsafe rate at or below alpha, and resolve as much as
    possible subject to that

Where to start, in the order the work happened
----------------------------------------------
    rule          the method. Clopper-Pearson calibration over a
                  pre-specified threshold grid, and the stopping rule.
    scorer        the score the threshold is applied to. Not where the
                  guarantee lives -- where the coverage lives.
    evaluate      the rule and the degenerate reference policies, scored on
                  unsafe rate, coverage and questions together.
    validate      the central experiment: calibrate and deploy repeatedly on
                  disjoint folds, count violations.

    robustness    does the bound survive a bad score? Eight corruptions, up
                  to the exact negation of a good one.
    conditional   where the error budget actually goes. It does not go where
                  the pooled number suggests.
    group         one threshold per group. Mondrian conformal prediction, and
                  the fix for what `conditional` finds.
    shift         what breaking exchangeability costs, measured rather than
                  asserted.
    power         how much data any of the above needs, in closed form,
                  before collecting it rather than after.

The one thing to read first
---------------------------
`docs/theory.md` separates what is proved from what is measured from what is
only empirically supported, and §4 is the finding that most changes what the
method is for: the guarantee is marginal, and on this benchmark the gap
between marginal and conditional is the difference between a 98.5% pass rate
and a 98.2% failure rate.

Nothing is re-exported from here. Every module's docstring carries its own
argument, and importing from `abstain.group` rather than `abstain` keeps a
reader one step from the reasoning instead of one step from a namespace.
"""

__version__ = "0.2.0"

__all__ = [
    "conditional",
    "evaluate",
    "group",
    "power",
    "robustness",
    "rule",
    "scorer",
    "shift",
    "validate",
]
