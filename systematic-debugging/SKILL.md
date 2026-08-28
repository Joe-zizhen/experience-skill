---
name: systematic-debugging
description: "Use when any technical issue — errors, crashes, failing tests or builds, regressions, wrong output, performance failures, integration failures, or other unexpected behavior — needs systematic root-cause diagnosis before any fix. Not for multi-cause or incident-grade analysis (→ 5w-ledger-v1-3); not for building features (→ senior-engineer)."
---

# Systematic Debugging

## Overview **[DEFAULT]**

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** the goal of diagnosis is the *minimal sufficient causal explanation* — enough understanding of the mechanism to choose the correct fix boundary. Do not chase an unattainable ultimate root cause. When the true origin is outside your control (upstream service, platform, vendor), fixing at the earliest boundary you *do* control is legitimate, as long as the boundary is named explicitly.

This plugin is a corollary of the suite law: undiagnosed faults. A green test is not completion. Wrong uncertainty type → switch plugin.

Symptom patches without a causal explanation are failure. Rules in this skill are tiered: **[INV]** invariants (violations are defects), **[DEFAULT]** standard policy (project facts or the user may override), **[HEURISTIC]** review signals (trigger a check, never a verdict by themselves), **[EXAMPLE]** illustrations (no normative force).

## The Iron Law **[INV]**

```
NO PERMANENT FIX WITHOUT A CAUSAL EXPLANATION SUFFICIENT TO CHOOSE THE FIX BOUNDARY
```

If you haven't completed Phase 1, you cannot propose permanent fixes.

**Stop-loss is not a fix (active-incident exception).** In a live production incident, reversible mitigations — rollback, flag off, traffic shift, node isolation — MAY run before causal investigation, provided they are reversible, observable, and quick to undo. Their purpose is to stop the bleeding, not to close the issue. Delivering a stop-loss as if it were the fix violates this law; the permanent fix still requires the causal explanation.

## When to Use **[DEFAULT]**

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

## The Four Phases **[DEFAULT]**

Work through the applicable phases in order. Scale the effort to the issue; the Iron Law above never scales.

### Phase 1: Causal Investigation **[DEFAULT]**

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - They often contain the exact solution
   - Read stack traces completely
   - Note line numbers, file paths, error codes

2. **Reproduce Consistently**
   - Can you trigger it reliably?
   - What are the exact steps?
   - Does it happen every time?
   - If not reproducible → gather more data, don't guess

3. **Check Recent Changes**
   - What changed that could cause this?
   - Git diff, recent commits
   - New dependencies, config changes
   - Environmental differences

4. **Gather Evidence in Multi-Component Systems**

   **WHEN system has multiple components (CI → build → signing, API → service → database):**

   **BEFORE proposing fixes, add diagnostic instrumentation:**
   ```
   For EACH component boundary:
     - Log what data enters component
     - Log what data exits component
     - Verify environment/config propagation
     - Check state at each layer

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify failing component
   THEN investigate that specific component
   ```

   **Example (multi-layer system) **[EXAMPLE]**:**
   ```bash
   # Layer 1: Workflow
   echo "=== Secrets available in workflow: ==="
   echo "IDENTITY: ${IDENTITY:+SET}"   # existence only: SET when set, empty otherwise — never prints the value

   # Layer 2: Build script
   echo "=== Env vars in build script: ==="
   env | grep -q IDENTITY && echo "IDENTITY present" || echo "IDENTITY not in environment"   # grep -q prints nothing: checks propagation without leaking the value

   # Layer 3: Signing script
   echo "=== Keychain state: ==="
   security list-keychains
   security find-identity -v

   # Layer 4: Actual signing
   codesign --sign "$IDENTITY" --verbose=4 "$APP"
   ```

   **This reveals:** Which layer fails (secrets → workflow ✓, workflow → build ✗)

5. **Trace Data Flow**

   **WHEN error is deep in call stack:**

   See `root-cause-tracing.md` in this directory for the complete backward tracing technique.

   **Quick version:**
   - Where does bad value originate?
   - What called this with bad value?
   - Keep tracing up until you find the source or the earliest boundary you control
   - Fix at that boundary, not at the symptom

### Phase 2: Pattern Analysis **[DEFAULT]**

**Find the pattern before fixing:**

1. **Find Working Examples**
   - Locate similar working code in same codebase
   - What works that's similar to what's broken?

2. **Compare Against References**
   - If implementing pattern, read reference implementation COMPLETELY
   - Don't skim - read every line
   - Understand the pattern fully before applying

3. **Identify Differences**
   - What's different between working and broken?
   - List every difference, however small
   - Don't assume "that can't matter"

4. **Understand Dependencies**
   - What other components does this need?
   - What settings, config, environment?
   - What assumptions does it make?

### Phase 3: Hypothesis and Testing **[DEFAULT]**

**Scientific method:**

1. **Form Single Hypothesis**
   - State clearly: "I think X is the root cause because Y"
   - Write it down
   - Be specific, not vague

2. **Test Minimally**
   - Change ONE variable at a time to test the hypothesis
   - Note: testing one variable is not the same as limiting the eventual fix to one file — a correct fix may be atomic across several files (see Phase 4)

3. **Verify Before Continuing**
   - Did it work? Yes → continue to Phase 4
   - Didn't work? Form NEW hypothesis
   - DON'T add more fixes on top

4. **When You Don't Know**
   - Say "I don't understand X"
   - Don't pretend to know
   - Ask for help
   - Research more

### Phase 4: Implementation **[DEFAULT]**

**Fix the cause at the chosen boundary, not the symptom:**

1. **Create Failing Test Case** — preferred proof, but not the only acceptable one
   - Simplest possible reproduction
   - Automated test if possible
   - One-off test script if no framework
   - When an automated test is genuinely impractical (hardware, timing, external service), an executable reproduction, monitoring probe, or independent verification is acceptable — write down why the automated test was impractical (required)

2. **Implement the Fix**
   - Address the causal explanation from Phase 1–3
   - The fix may be atomic across multiple files when the mechanism requires it
   - No "while I'm here" improvements
   - No bundled refactoring

3. **Verify Fix**
   - Test passes now?
   - No other tests broken?
   - Issue actually resolved?

4. **If Fix Doesn't Work**
   - STOP
   - Count: How many fixes have you tried?
   - If < 3: Return to Phase 1, re-analyze with new information
   - **If ≥ 3: STOP and review your problem model (below)**
   - DON'T attempt Fix #4 without that review

5. **If 3+ Fixes Failed: Review the Problem Model**

   Repeated failure triggers a **review of the problem model**, not a verdict about architecture. Candidates to examine with your human partner:
   - Wrong assumptions about the mechanism
   - Insufficient observation (missing instrumentation or logs)
   - Multiple independent defects being mistaken for one
   - An architectural problem (pattern fundamentally unsound, kept alive through inertia)

   **Discuss with your human partner before attempting more fixes.** The output of this review is a decision: new hypothesis, better instrumentation, split the defects, or architecture change.

## Red Flags - Review Triggers **[HEURISTIC]**

These thoughts are **signals to pause and re-examine**, never proof by themselves:

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- "One more fix attempt" (when already tried 2+)
- Each fix reveals new problem in different place

When several of these fire, stop and return to Phase 1 with fresh eyes.

## Your Human Partner's Signals You're Doing It Wrong **[HEURISTIC]**

**Watch for these redirections:**
- "Is that not happening?" - You assumed without verifying
- "Will it show us...?" - You should have added evidence gathering
- "Stop guessing" - You're proposing fixes without understanding
- "Ultrathink this" - Question fundamentals, not just symptoms
- "We're stuck?" (frustrated) - Your approach isn't working

**When you hear these:** pause and check whether you skipped Phase 1.

## Common Rationalizations **[EXAMPLE]**

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic diagnosis is usually faster than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = review the problem model, don't fix again. |

## Quick Reference **[DEFAULT]**

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Causal** | Read errors, reproduce, check changes, gather evidence | Understand mechanism enough to choose fix boundary |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |

## When Process Reveals "No Root Cause" **[DEFAULT]**

If systematic investigation shows the issue is truly environmental, timing-dependent, or external:

1. You've completed the process
2. Document what you investigated
3. Implement appropriate handling (retry, timeout, error message)
4. Add monitoring/logging for future investigation

**But:** treat "no root cause" as a claim that needs evidence — most cases are incomplete investigation.

**Reclassification:** if the investigation shows the problem is not a technical fault at all (requirement error, design constraint, expectation mismatch), stop — declare the evidence and switch to the matching plugin (`pm` / `first-principle-v2`). Envelope optional. Do not force a technical fix to fit a wrong problem model.

**Completion is a reality property:** a fix is complete when the failure disappears in the real environment and does not return during the observation window — not when the test turns green or the writeup is finished.

## Handoff envelope **[DEFAULT]**

可选。单独修完不必写。只有真要把上下文交给另一个 skill 时才写这块。没有的字段写「无」：

- 看见了什么
- 本该怎样
- 怎么复现
- 证据
- 机制或猜想（够选修复边界，或写还不够）
- 把握
- 范围
- 没查清的
- 红线
- 怎样能推翻
- 谁拍板
- 最小可退的下一步

## Supporting Techniques **[DEFAULT]**

These techniques are part of systematic debugging and available in this directory:

- **`root-cause-tracing.md`** - Trace bugs backward through call stack to find original trigger
- **`defense-in-depth.md`** - Add validation at trust, ownership, and irreversible-effect boundaries
- **`condition-based-waiting.md`** - Replace arbitrary timeouts with condition polling
