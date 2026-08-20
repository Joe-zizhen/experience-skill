# Migration Decomposition (first-principle-v2)

Step 6 second half: turning a target architecture into independently verifiable steps.

## Rules

Decompose the incremental migration into a sequence of **independent, verifiable intermediate states**. Each state must keep the system operational and pass existing tests. For each step define:

- **Precondition**: what must be true before this step starts.
- **Change scope**: what code, config, data, or infrastructure changes in this step.
- **Rollback**: how to revert this step independently. If a step cannot be rolled back, label it an irreversible decision point and assess the risk explicitly.
- **Validation signal**: the observable metric, test, or behavior that confirms the step succeeded.

If any step cannot be made independently verifiable or reversible, stop and reconsider whether the target architecture can be reached through a different sequence, or whether the risk of that step is acceptable.

## Parallelism

When multiple migration steps have no coupling between them — different components, different teams, no shared state or contract — they may be pipelined in parallel rather than sequenced. Name the coupling that prevents parallelism; if none exists, state that the steps are independent and may overlap in time.
