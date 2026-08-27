# Consuming a 5W Handoff (first-principle-v2)

How first-principle design consumes a 5w-ledger RCA handoff.

## What to consume

If a shared envelope is present, prefer it (write-ins of `无` mean the field does not apply): 看见了什么 / 本该怎样 / 怎么复现 / 证据 / 机制或猜想 / 把握 / 范围 / 没查清的 / 红线 / 怎样能推翻 / 谁拍板 / 最小可退的下一步. If none is present, proceed from the RCA you have; do not stall waiting for a baton.

Also take, when present:

- The desired invariant
- The causal mechanism
- The problem structure characterization (single-point defect / structural absence / boundary condition)
- Evidence and confidence
- Relevant control gaps
- Unknowns

Treat `probable` or `hypothesis` causes as **assumptions to validate** before irreversible design. Derive the design from the handoff; do not accept a diagnosis-stage solution by default.

## Verification duty

When the materials the handoff cites remain accessible — the supplied case narrative, if any, and any reachable system evidence — verify the handoff's **load-bearing facts, reconciliations, and stated checks** against them before any irreversible design step. This is targeted verification of designated claims, not re-diagnosis.

- A handoff claim that fails verification degrades to an unverified assumption.
- A reconciliation or stated check passes verification only when its premise is itself stated in the materials or independently observed; a plausible but unstated premise fails verification.
- In a closed narrative, verification means checking claims against the supplied narrative itself, not demanding evidence that does not exist.
