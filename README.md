# A selection rule that bounds how often an agent answers blind

## The failure this exists to fix

A companion benchmark measured a frontier model conducting benefits intake
interviews. Given cases that **cannot be decided** from the information
available, it answered anyway **62.5%** of the time. Downstream, each of those
is a filed claim built on a guess.

The reference policies bracket the problem:

| Policy | Unsafe | Wasted questions | Questions/case |
|---|---:|---:|---:|
| Answer immediately | **91.7%** | 0% | 0.00 |
| Ask everything | 0% | **44.4%** | 3.00 |
| Abstain if anything unknown | 0% | 0% | — resolves nothing |
| Oracle ceiling | 0% | 0% | **1.67** |

Each degenerate policy fails differently. Safety is free if you refuse to act;
coverage is free if you never check. **The open question is whether a rule can
hold a stated unsafe rate while resolving materially more than the safe
heuristic.**

## Status

**Nothing is built yet.** This commit contains the benchmark split and nothing
else, which is deliberate.

## The holdout is locked before the method exists

The failure mode of a method paper is tuning against the evaluation until it
wins. It is rarely deliberate — it happens one reasonable decision at a time.

So the split is the first commit. The git history is the evidence that it
precedes every line of method code.

| | Cases | Composition |
|---|---:|---|
| **dev** | 8 | built on, tuned on, looked at freely |
| **holdout** | 8 | opened once, when the method is final |

Stratified by the share of each case's knowledge states that are
underdetermined, so both halves carry comparable mixes rather than one
collecting the decidable problems.

Each half ships a SHA-256. A later run producing different contents is visible
rather than silent, and `tests/` asserts the committed digests still match.

**A result on dev is a demonstration. A result on holdout is a result.**

## License

MIT. Derived from the `underdetermined` benchmark in the same account.
