# Pattern Recruitment (first-principle-v2)

Step 7 bounded pass: when to import known engineering patterns.

## When to run it

Run one bounded pattern-recruitment pass when the core needs involve **overload, capacity, outage or cascading-failure mechanics, or dormant-defect shapes**. Degradation of quality metrics without those shapes does not trigger the pass; when no pattern applies, state none and move on.

## How to run it

1. **State the semantics of the data** (state vs event, ordered vs unordered, authoritative vs cacheable) and the **second-order dynamics** (how clients, users, and retries respond to the failure).
2. Ask which known engineering pattern classes address this failure shape — for example conflation, backoff/jitter, backpressure, freeze windows, or evidence-gated decision records — and import them as candidates.

## Discipline

Imported patterns are **hypotheses entering validation, not conclusions**: each must map to an observed mechanism in the evidence and earn its complexity like any other candidate. Keep conventions that earn their place through domain knowledge, integration value, or reduced risk; discard those that do not.
