---
name: first-principle-v2
description: "Use for deliberate first-principles design: major or hard-to-reverse decisions, unresolved assumptions that change the answer, or explicit first-principles requests. Derive the simplest correct solution from foundational facts; default output is a design or decision, not code."
---

# First Principle Thinking

Use first-principle thinking to design forward from foundational facts instead of copying existing patterns. The default output is a design or decision, not an implementation. Strip away assumptions, identify irreducible truths and constraints, then derive the simplest solution that directly satisfies them. The simplest correct solution minimizes total lifecycle complexity, not merely code size or component count.

Rule tiers: **[INV]** invariant (violation is a defect), **[DEFAULT]** standard policy, **[HEURISTIC]** review signal, **[EXAMPLE]** illustration.

## Workflow **[DEFAULT]**

1. **Define the target outcome in one sentence**: what must become observably true, how success will be judged, and the relevant time horizon. Do not embed a preferred implementation unless it is a real constraint.
2. **Separate decision inputs**: observed facts / required outcomes / constraints / assumptions. Classify each constraint — **design constraints** (challengeable; authority derives from the decision that made them) vs **accretion constraints** (boundary conditions for this design; changing them is a separate project). A user statement is a requirement or claim, not automatically an observed fact. Detailed taxonomy, external date-locked constraints, and team-capability handling: [references/constraint-taxonomy.md](references/constraint-taxonomy.md).
3. **Challenge every decision-shaping assumption and every constraint** whose authority, necessity, or factual basis is not established. For each challenged design constraint, name the decision-owner with override authority and the minimum evidence that would reopen it; unknown owner or threshold → staged decision gate (step 7).
4. **Decompose** the problem into needs, capabilities, and invariants until the remaining elements are basic and hard to dispute. Each need must name a capability the system provides, not restate a required outcome; if it restates one, decompose one level deeper.
5. **Verify observed-fact consistency before rebuilding**: any alternative rejected against a factual claim must not contradict a listed observed fact — resolve the conflict first (downgrade the fact, reconsider the rejection, or narrow the rejection's scope). Then rebuild the smallest design that satisfies outcomes and constraints with least total lifecycle complexity. Close each material invariant by naming its authoritative owner, enforcement boundary, failure behavior, and recovery path — in proportion to material risk.
6. **Brownfield gate: patch-pile threshold.** Skip for greenfield. For components with existing code, evaluate whether accumulated patches have crossed the rewrite threshold (signal: drift and coupling, not count): [references/rewrite-threshold.md](references/rewrite-threshold.md). If migration is needed, decompose it into independently verifiable, independently reversible steps: [references/migration.md](references/migration.md).
7. **Compare against current and conventional approaches only after deriving the baseline.** When the request names a technology or architecture, first derive a technology-neutral baseline and a no-new-component option; retain the named choice only if it measurably earns its complexity. For overload/cascading-failure/dormant-defect shapes, run one bounded pattern-recruitment pass: [references/pattern-recruitment.md](references/pattern-recruitment.md). Generate multiple candidates only when material uncertainty remains; do not manufacture weak alternatives. Under material uncertainty, choose the most reversible viable course and turn unresolved evidence into a staged decision gate — never use "more research" as a substitute for a decision when a bounded choice is possible.
8. **Explain why the solution is not more complex**: map each included element to a required outcome, constraint, or material risk, and name what was intentionally excluded.
9. **Define validation**: tests, prototypes, measurements, user checks, acceptance and falsification criteria. Test the cheapest decision-changing assumption early and the highest-risk assumption before irreversible investment. For each material gate: hypothesis, cheapest discriminating test, pass/fail threshold when measurable, action on success, fallback on failure. State whether an unresolved fact blocks the decision or only a later stage, and what evidence would reverse it.
10. **One blind-spot pass** before finalizing: the biggest missing fact, constraint, stakeholder, assumption, or second-order effect. If material, revise once. Stop when the next concern is speculative, low-impact, or not actionable.
11. **Implementation boundary [INV]**: without implementation authorization, stop at design — name the required approval or input. When authorized, complete the design checkpoint before continuing.

## Guardrails **[DEFAULT]**

- Do not use first principles as an excuse to ignore proven constraints or domain knowledge.
- Do not over-decompose routine tasks unless explicitly invoked.
- Do not implement by default; follow the implementation boundary.
- Ask clarifying questions when a foundational fact is missing and guessing would change the solution.
- Prefer reversible decisions under material uncertainty.
- **State uncertainty directly. Unmeasured quantities stay UNKNOWN — never fabricate precise-looking thresholds, scores, or statistics without a measured source.**
- Preserve the existing codebase style and contracts unless a first-principle argument clearly justifies changing them.
- Exclude speculative extensibility, premature abstraction, and features that do not serve a required outcome or mitigate a material risk.
- Maintain decision density: include a fact, decomposition, alternative, or check only when it changes the selected course, its boundary, a material risk, or the validation order.

## Conditional Checks **[DEFAULT]**

- For technology choices, verify current official or primary recommendations, versions, maintenance status, security posture, compatibility, and ecosystem maturity. If verification is unavailable, keep the claim as an assumption. Newer is not automatically better.
- For costly, high-risk, or hard-to-reverse decisions, examine failure modes, reversibility, migration and rollback, operational ownership, and staged validation gates.
- For a 5W handoff, consume it per [references/5w-handoff.md](references/5w-handoff.md): treat `probable` or `hypothesis` causes as assumptions to validate before irreversible design, and verify the handoff's load-bearing facts against the cited materials when they remain accessible.

## Output Shape **[DEFAULT]**

Provide:

- Desired outcome
- Observed facts, required outcomes, and constraints (with design vs accretion classification)
- Current technology facts, if relevant
- Decision-shaping assumptions challenged and their status, if any
- Derived baseline and alternatives when material
- Selected solution and why it is not more complex
- **Incremental migration path** — when the change touches existing consumers, state, data, or contracts (per [references/migration.md](references/migration.md)); for a localized change with no consumer or state impact, state in one sentence why none is needed. Greenfield: skip.
- Blind-spot check
- Tradeoffs and reversibility
- Validation plan and decision-reversal conditions
- Implementation boundary / next action

For a small decision, combine sections while preserving decisive facts or constraints, material challenged assumptions, derivation, exclusions, and validation.
