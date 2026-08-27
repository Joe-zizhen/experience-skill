---
name: 5w-ledger-v1-3
description: "Evidence-based Five Whys root cause analysis with an observable evidence ledger. Use only for high-severity incidents, failures spanning a time window or multiple interacting causes — including 'which change introduced it' questions — audit/postmortem reviews, and handoffs. Not for routine localized bug fixes."
---

# 5W Ledger Root Cause Analysis

Use Five Whys as an evidence-based reverse diagnosis method. Reduce an observed failure to a causal problem statement that can be handed to solution design.

Rule tiers: **[INV]** invariant (violation is a defect), **[DEFAULT]** standard policy (facts or the user may override), **[HEURISTIC]** review signal, **[EXAMPLE]** illustration.

## When To Use This Skill **[DEFAULT]**

Run the full ledger workflow when any of these holds:

- The user explicitly asks for an evidence ledger or an auditable RCA.
- The incident is high-severity, spans a time window, or has multiple candidate or interacting causes.
- The result feeds an audit, a postmortem, or a handoff to another agent or team.
- The evidence base is a supplied closed narrative with no live systems to inspect.

Do **not** run it for routine localized bug fixes with one obvious cause, style or explanation questions, or general chat — normal debugging and a plain answer are cheaper and better. If you are already inside the workflow and the failure proves localized and well-evidenced, switch to the compressed form defined in Output Shape; never abandon evidence discipline mid-analysis.

## Evidence Acquisition **[DEFAULT]**

When a repository or live system is accessible, gather evidence in this order and stop as soon as every material link has support:

1. Recent changes first: deployment times, config and feature-flag changes, `git log` / `git diff` over the failure window, traffic shifts.
2. The failure signature: exact error text, stack trace, first-error timestamp, affected cohorts, recovery events. Reproduce when practical.
3. Follow the error path: from the log line or entrypoint into the failing code; read the relevant code, config, and tests before naming any cause.
4. Stop when existing evidence covers each material link — one artifact may support several links; do not collect new evidence mechanically.

Record what you inspected (paths, commands, log excerpts, timestamps) so each ledger row can cite it **and name its source type**: 用户陈述 (user statement) / 闭合叙事 (closed narrative) / 代码 (code) / 日志 (logs) / 复现 (reproduction) / 外部文档 (external doc). With a supplied closed narrative instead, quote the case text as the supporting fact and apply the closed-evidence rules in Workflow step 2 and the precedence gate in step 6.

Evidence comes in two generations. **Existing evidence** is what you collect without executing the system under investigation: logs, code reading, configs, git history, deployment records, user statements, external docs — no matter how many read-only commands you run, it remains existing evidence. **Generated evidence** exists only because the system was executed under your control: a reproduction with its observed output, an instrumented run (debugger, trace, or temporary logging), a single-variable experiment, or a counterfactual/comparison run (method: follow systematic-debugging Phase 1/3 — referenced here, not copied). Record generated evidence under source type 复现, citing the executed command and its observed result.

## Workflow **[DEFAULT]**

1. State the observed symptom precisely: impact, scope, time window, actual behavior, expected behavior, and reproduction conditions when known. Separate observation from interpretation. Define the analysis boundary, relevant control boundary, and expected invariant when they materially affect what counts as a root cause.
2. For code-related problems, inspect the relevant code, configuration, tests, logs, and runtime evidence before proposing any cause. **For failures spanning time windows, collect the timeline and verify that each causal link's cause precedes its effect.** For a supplied closed narrative (no live systems), facts stated in the case are admitted as stated and carry narrative-grade confidence (no higher than `probable`); every material link that relies solely on the narrative is capped at `probable`, with the missing artifacts named as verification needs. `confirmed` is reserved for links supported by direct observation, reproduction, or strong converging evidence.
3. Before accepting each Why answer, require evidence for that causal link: logs, code paths, configs, tests, timelines, user reports, deployment history, or reproducible steps. **In live-system investigations, classify every material link's evidence as existing or generated (see Evidence Acquisition).** Every material link left UNRESOLVED or `probable` must carry an **executable verification step**: a specific command or experiment plus its expected discriminating outcome — which observation would confirm the link and which would falsify it. If the step cannot be run now, name the missing environment, access, or artifact. Non-executable phrasings ("collect more logs", "investigate further") do not count as verification steps.
4. Build an explicit Why chain. Each answer must causally explain the preceding effect and state the cause, mechanism, evidence, source type, and confidence; do not jump to a preferred theory. When independent or converging causes are necessary, branch into multiple Why chains instead of forcing one linear story. Keep the evidence scope explicit for every chain.
5. Separate categories clearly:
   - Symptom: what was observed.
   - Trigger: the event or condition that initiated the failure sequence.
   - Direct cause: what immediately produced the symptom.
   - Contributing causes: conditions that made it possible or worse.
   - Root cause or causes: the deepest evidence-supported causal conditions within the defined analysis scope.
   - Control gap: the modifiable system, process, design, ownership, or assumption condition that allowed the consequence or recurrence, when distinct from the causal origin.
   - Detection or response gap: why the failure escaped, persisted, or worsened; do not mislabel it as the runtime cause.
6. Test material causal links and the strongest plausible rival explanation. Require temporal order and a credible mechanism; when practical, use reproduction, comparison, change correlation, or a counterfactual. Treat correlation alone as insufficient. **Skipping reproduction or experiment for a material link in a live-system investigation requires a written reason why it was impractical; a silent skip is a violation.** For closed evidence, apply this precedence gate before accepting any causal link, root-cause label, verification need, or final problem statement:
   - If a specific property or mechanism is not stated or favored by the given facts, mark that link **UNRESOLVED**; calling it a hypothesis does not admit it.
   - If evidence contradicts a concrete claim as stated, mark it **REFUTED** and name the contradicting fact.
   - If evidence establishes no root cause for a branch, end with `root cause not established`; the output shape does not require every branch to have a root cause.
   - Name the discriminating evidence to obtain, not specific possible causes or possible evidence results.
   - Copy the narrowest material scope and lowest confidence literally into every root-cause label and final problem statement.
   This gate overrides chain completeness, preferred depth, rival-detail, and output-shape completeness. In live or code investigation, a concrete hypothesis may guide a distinct obtainable check, but test it before accepting it. When the user explicitly requests exhaustive hypotheses, list material candidates separately and keep them out of the accepted chain until validated.
   **When multiple causal branches must intersect for the failure to occur, name the minimal sufficient causal set — the conjunction of conditions without which the failure would not have occurred — and identify which members are within the defined control boundary.**
   Example: "Memory leak alone was insufficient; the spike in concurrent requests alone was insufficient. The minimal sufficient causal set is {memory leak, traffic spike}. Within the control boundary, the memory leak is the actionable root cause. The traffic spike is a boundary condition the system is expected to tolerate at some threshold."
   If independent branches each cause the failure in different cohorts, time windows, code paths, or failure modes, keep them as separate causal branches rather than forcing a single set.
7. Stop when the next Why would become speculation, blame, immaterial to the problem definition, outside the chosen analysis scope, or solution design instead of cause analysis. The smallest evidence-closed mechanism is sufficient. Do not stop solely because a fact is unchangeable: record it as a boundary condition and, if the system was expected to tolerate it, ask why the consequence remained possible.
8. Run one bounded blind-spot pass before finalizing. Check the strongest rival explanation, a missing causal branch, missing or biased evidence, and the reconciliation of stated quantities — if two or more stated numbers bear on the same causal link, verify they are arithmetically consistent. An inconsistency does not falsify the causal identity, but the reconciliation is marked UNRESOLVED with the discriminating evidence named. A reconciliation achieved only by supplying an unstated premise is not a reconciliation: treat the premise as an unverified assumption and mark the reconciliation UNRESOLVED. Treat separate cohorts, failure modes, and cases independently unless direct evidence establishes a shared causal mechanism. If the pass reveals a more fundamental evidence-backed cause that changes the chain, revise it once. Stop when the next concern is speculative, low-impact, or unsupported.
9. Return the actual problem as a concise, solution-neutral engineering statement: "The real problem is: under X condition, A produced Z through mechanism M, violating invariant I." Copy the supporting chain's narrowest material scope and lowest confidence explicitly into the statement. A `probable`, `hypothesis`, or UNRESOLVED link must not become a confirmed or broader claim in the summary. State a distinct control gap separately when relevant.
10. If confidence is incomplete, label the cause as a hypothesis and state the evidence needed to confirm or falsify it. **Unmeasured quantities stay UNKNOWN — never generate precise-looking thresholds or statistics that have no measured source.**
11. **Characterize the problem structure** to constrain the solution space without prescribing a fix. Based solely on the causal evidence admitted in the ledger, identify which defect shapes are present (more than one may coexist):
    - **Single-point defect**: a localized error or omission whose effects propagate from that point.
    - **Structural absence**: the mechanism operates through a missing contract, abstraction, invariant enforcement, or ownership boundary.
    - **Boundary condition**: an external or accreted constraint the system was expected to tolerate but could not.
    When evidence is insufficient to distinguish between shapes, state UNRESOLVED with the discriminating evidence needed. State the rationale for each identified shape in one sentence. Do not evaluate fix invasiveness, cost, priority, or implementation approach here.
12. Provide a handoff for first-principle solution design only when the user requests solution design, remediation, or a combined 5W-to-first-principle workflow. Otherwise stop after the RCA and verification needs. When requested, include the desired invariant, observed failure, Why chain or causal tree, root cause or causes, problem structure characterization, relevant control or detection gaps, evidence and confidence, competing hypotheses, unknowns, the falsifier for each material conclusion (what evidence would overturn it), the decision owner, and the minimal reversible next action. Do not embed a preferred solution.

## Guardrails **[DEFAULT]**

- Do not edit files, modify code, change configuration, or implement fixes while constructing the RCA. If the current request authorizes later stages, complete the RCA handoff before continuing.
- Do not turn the root cause into a proposed solution.
- Do not treat "human error" as a root cause. Ask why the system allowed the error.
- Do not force exactly five whys. Use only as many as the evidence supports.
- Do not invent evidence. If evidence is missing, say what must be inspected next.
- Do not name a root cause from memory, intuition, prior impressions, or conversation context alone. For code-related issues, inspect the relevant code or state that the root cause is unconfirmed.
- Use `confirmed` only for direct observation, reproduction, or strong converging evidence; `probable` when the evidence favors one mechanism over material rivals and the remaining uncertainty does not change causal identity or scope; `hypothesis` when missing evidence could change causal identity or scope. If multiple labels apply, use the lower one.
- In live-system investigations, split material links before assigning confidence. **Static-fact links** (a config value, code content, a version, a timeline fact): direct observation of the artifact may support `confirmed`. **Runtime-mechanism links** (asserting X produced Y through mechanism M at runtime): `confirmed` requires at least one piece of generated evidence for that exact link — an executed reproduction, an instrumented run (debugger, trace, or temporary logging), a single-variable experiment, or a counterfactual/comparison run, cited with its command and observed result. A mechanism link supported only by existing evidence caps at `probable`. Closed-narrative caps are unchanged.
- Treating log reading, code reading, or memory as if it were reproduction — and labeling a runtime-mechanism link `confirmed` on that basis — violates the confidence discipline.
- Preserve scope: never extend a cause beyond the samples, cohorts, time windows, code paths, or failure modes actually explained by its evidence.
- Preserve confidence: summaries, root-cause labels, and problem statements must not be more certain than the weakest material link in their supporting chain.
- Analyze multiple cases independently. Do not add cross-case analogies or shared-root theories unless the user explicitly asks for synthesis and the shared mechanism is directly evidenced.
- Do not treat a missing test or alert as the runtime cause unless it causally enabled the failure; otherwise classify it as a prevention, detection, or response gap.
- Prefer the smallest confirmed root problem over a grand theory.

## Output Shape **[DEFAULT]**

Provide:

- Observed symptom, impact, and scope
- **Timeline** (when relevant to establishing temporal order)
- Evidence inspected (with source types)
- Why chain or causal tree, including mechanism, evidence, source type, and confidence for each material link. **When branches intersect, name the minimal sufficient causal set and distinguish within-boundary members from boundary-condition members.**
- Direct and contributing causes; root causes only for branches where evidence establishes them, otherwise state `root cause not established`; control, detection, or response gaps when relevant
- Strongest material rival explanation, if any, and blind-spot check
- Actual problem statement
- Confidence, unknowns, and verification needed — each verification need written as an executable step (specific command or experiment plus expected discriminating outcome), per Workflow step 3
- **Problem structure characterization** (single-point defect / structural absence / boundary condition) with one-sentence rationale
- Handoff to first-principle input, only when requested — then emit the shared envelope (write `无` if a field does not apply): 看见了什么 / 本该怎样 / 怎么复现 / 证据 / 机制或猜想 / 把握 / 范围 / 没查清的 / 红线 / 怎样能推翻 / 谁拍板 / 最小可退的下一步. Standalone RCA does not need an envelope.

**Compressed form** — for a localized, well-evidenced failure: merge the headings into one short narrative and keep the ledger to the 3–6 material claims, but never omit the causal chain, the root problem, confidence, or the decisive verification, and always keep the two-section output contract. **Full form** — for a high-impact or multi-causal incident: include every heading above.

## Evidence Admission Ledger **[DEFAULT]**

Before writing the RCA, make evidence admission observable. Produce the ledger in a single pass, **before** the RCA: it is a decision record, not private chain-of-thought, and the RCA that follows may only use what the ledger admits. Apply the precedence gate in Workflow step 6 before instantiating a concrete claim in the ledger.

Cover every material causal link or root-cause claim, one row per claim:

- Claim ID (C1, C2, ...)
- Proposed causal claim
- Exact supporting facts: a quote from the supplied case, or an artifact reference (file:line, command output, log excerpt, timestamp)
- **Source type**: 用户陈述 / 闭合叙事 / 代码 / 日志 / 复现 / 外部文档
- Supported scope
- Confidence
- Missing premise, if any
- Decision: `ADMIT`, `REFUTED`, or `UNRESOLVED`

Keep it compact: one or two lines per row, and merge claims that share the same evidence and decision. A typical incident needs 5–12 rows; the compressed form needs 3–6. If a draft ledger exceeds ~15 rows, merge or drop immaterial claims instead of growing the table.

Apply these rules:

1. Evaluate every causal link independently. Evidence for a candidate event does not transfer to its prerequisites, affected-object identity, hidden attributes, or intermediate links.
2. Use `ADMIT` only when the case states or favors that exact link at the stated scope and confidence.
3. Use `REFUTED` only when evidence contradicts the concrete claim as stated — name the contradicting fact. Use `UNRESOLVED` when evidence is insufficient to admit or refute; it marks the open boundary of the current RCA, and the discriminating evidence to obtain must be named without predicting the specific cause or result it will reveal. Neither decision precludes reassessment when that evidence arrives. A `hypothesis` label admits nothing.
4. Strong evidence for a candidate event may justify reporting it as a candidate, but does not establish that it affected the observed objects.
5. Build the final RCA only from `ADMIT` rows. `UNRESOLVED` may appear only as an explicitly open boundary. No final root-cause label or problem statement may introduce a claim absent from the ledger or broaden its scope or confidence.
6. Do not propose remedies. Keep confirmed mechanisms confirmed; do not become conservative when direct observation, reproduction, or strong converging evidence closes the exact link.
7. In live-system investigations, an `ADMIT` at `confirmed` confidence for a runtime-mechanism link must cite at least one generated-evidence row (source type 复现) with the executed command and its observed result. Verification needs must be written as executable steps per Workflow step 3.

## Output Contract **[DEFAULT]**

The default output is exactly two top-level sections, in this order:

```
<ledger>
The compact evidence admission ledger: one row per material claim.
</ledger>

<final>
The complete RCA per Output Shape, built only from ADMIT rows plus
explicitly open UNRESOLVED boundaries.
</final>
```

**Format override:** when the user specifies another format (JSON, Markdown template, or any other), the user's format wins — but it must still carry the ledger (with decisions) and the final RCA built only from ADMIT rows; the two-section semantics are preserved, the packaging changes.

**Prefix exemption:** a host- or project-mandated metadata prefix (such as an experience-gate hit marker) may precede `<ledger>` and does not violate this contract; the two sections remain the entire content body.

The `<final>` section is the deliverable. Make it self-contained: cite evidence and confidence inline, and do not reference the ledger, admission mechanics, or these instructions. A reader who skips `<ledger>` must still get the complete RCA.

Default length: at most ~1,500 words (ledger included) for the full form, ~600 for the compressed form, unless the user sets a different budget. Spend the budget on causal links and evidence, not on restating the symptom.
