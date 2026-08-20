# Constraint Taxonomy (first-principle-v2)

How to classify and treat each kind of constraint in step 2.

## Design constraints vs accretion constraints

**Design constraints**: intentional choices (architecture patterns, framework selections, API contracts, data schemas). They can be challenged and re-evaluated against first principles. Their authority derives from the decision that created them; if that decision's rationale no longer holds, the constraint may be overturned.

**Accretion constraints**: emergent facts from system evolution (compatibility contracts exposed to external consumers, implicit data consistency dependencies, regulatory obligations, irreversible data migrations). They cannot be changed within the scope of the current design without an independent migration project. Accept them as boundary conditions for this design but **do not replicate them into new components**. An accretion constraint binds the compatibility *surface* (e.g., the test-observation boundary, the API contract signature), not the internal design of new components built behind that surface.

If classification is uncertain — the item's mutability or authority cannot be established from available evidence — do not default to accretion. Flag it as an unresolved classification, design the most reversible viable path that does not depend on the classification being right, and treat resolving it as a staged decision gate.

## External date-locked constraints

Regulatory deadlines, contract expiry, certification clocks, attrition dates are hard constraints with a fixed calendar date. When the design window contains multiple such dates, compute the timeline arithmetic **before** accepting any stated delivery target — the most constraining external date sets the true deadline. A stated delivery target that is arithmetically incompatible with the external date chain is a design constraint, not a hard deadline: challenge it as such.

## Team capability

Expertise distribution, institutional knowledge, team size, and turnover are soft feasibility inputs, not design boundaries. They do not eliminate candidates; they adjust execution:

- Reduce migration step size so each step is independently completable by the available expertise.
- Increase documentation and handoff checkpoints in proportion to knowledge risk.
- When a candidate requires capability the team lacks, treat the gap as a staged learning gate (spike, consultant, pair-programming) rather than a hard veto — unless the learning window exceeds the design's time constraint.
- When capability is carried by specific individuals with fixed departure dates, the departure date itself is a hard accretion constraint on the schedule: the knowledge must be captured or the dependency removed before that date, independent of whether the capability gap can be learned by others.
