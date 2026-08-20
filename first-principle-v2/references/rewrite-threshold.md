# Patch-Pile Threshold (first-principle-v2)

Step 6 gate for brownfield components: rewrite or repair?

## The gate

Has the current implementation accumulated **divergent copies of the same logic** that have already drifted apart and would require coordinated changes to keep in sync, or **special-case branches** that route around the core rule?

- The signal is *drift* (copies that have diverged and will keep diverging with each future change) and *coupling* (a change at one site requires coordinated changes at others), **not count alone**.
- The *affected component* is the minimal unit owning the defect — scope any rewrite to that unit, and reuse stable pieces (APIs, contracts, data schemas, external Activity/Intent contracts) rather than rewriting them.
- Hard constraints short-circuit the gate: if a full-app rewrite is forbidden, the gate evaluates only component-scoped rewrites.

## If the gate fires (rewrite justified)

Carry the rewritten design into the candidate comparison as a named candidate alongside the incremental and no-new-component options, with the same four-part discipline:

- **Precondition**: what must be true before the rewrite starts.
- **Change scope**: the minimal affected component being replaced, preserving stable contracts and hard constraints.
- **Rollback**: how to revert the rewrite independently (if unrevertable, label it an irreversible decision point and assess the risk).
- **Validation signal**: the observable metric, test, or behavior that confirms the rewrite succeeded.

## If the gate does not fire

When the change is localized and touches no existing consumers, state, data, or contracts, state in one sentence that no migration path is needed and why. Otherwise decompose the migration per [migration.md](migration.md).
