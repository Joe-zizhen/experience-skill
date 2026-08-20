# Condition-Based Waiting

## Overview **[DEFAULT]**

Flaky tests often guess at timing with arbitrary delays. This creates race conditions where tests pass on fast machines but fail under load or in CI.

**Core principle:** Wait for the actual condition you care about, not a guess about how long it takes.

## When to Use **[DEFAULT]**

**Use when:**
- Tests have arbitrary delays (`setTimeout`, `sleep`, `time.sleep()`)
- Tests are flaky (pass sometimes, fail under load)
- Tests timeout when run in parallel
- Waiting for async operations to complete

**Don't use when:**
- Testing actual timing behavior (debounce, throttle intervals)
- Always document WHY if using an arbitrary timeout

## Core Pattern **[EXAMPLE]**

```typescript
// ❌ BEFORE: Guessing at timing
await new Promise(r => setTimeout(r, 50));
const result = getResult();
expect(result).toBeDefined();

// ✅ AFTER: Waiting for condition
await waitFor(() => getResult() !== undefined, 'result defined');
const result = getResult();
expect(result).toBeDefined();
```

## Quick Patterns **[EXAMPLE]**

| Scenario | Pattern |
|----------|---------|
| Wait for event | `waitFor(() => events.find(e => e.type === 'DONE'), 'DONE event')` |
| Wait for state | `waitFor(() => machine.state === 'ready', 'ready state')` |
| Wait for count | `waitFor(() => items.length >= 5, '5 items')` |
| Wait for file | `waitFor(() => fs.existsSync(path), 'file exists')` |
| Complex condition | `waitFor(() => obj.ready && obj.value > 10, 'ready and >10')` |

## Implementation **[DEFAULT]**

**Preference order:** if your source supports event *subscription* (EventEmitter, Observable, callback registration), subscribe instead of polling — polling is the fallback for query-only APIs.

See `condition-based-waiting-example.ts` in this directory for the hardened implementation. Non-negotiable properties of any `waitFor` you write:

- **Monotonic clock** (`performance.now()` or equivalent) — wall-clock time can jump and fake a timeout or extend it.
- **Configurable poll interval** — never hardcode the interval in callers.
- **Cancellation** — accept an `AbortSignal` (or your platform's equivalent); a wait that can't be cancelled hangs suites.
- **Predicate errors reject** — a throwing or rejecting predicate (sync or async) must reject the returned Promise. A predicate exception is a defect in the test, and swallowing it turns a broken test into a mysterious timeout.

## Common Mistakes **[HEURISTIC]**

**❌ Polling too fast:** `setTimeout(check, 1)` - wastes CPU
**✅ Fix:** Poll on a sensible interval (e.g. 10ms) and make it configurable

**❌ No timeout:** Loop forever if condition never met
**✅ Fix:** Always include timeout with clear error

**❌ Stale data:** Cache state before loop
**✅ Fix:** Call getter inside loop for fresh data

## When Arbitrary Timeout IS Correct **[DEFAULT]**

```typescript
// Tool ticks every 100ms - need 2 ticks to verify partial output
await waitForEvent(manager, 'TOOL_STARTED'); // First: wait for condition
await new Promise(r => setTimeout(r, 200));   // Then: wait for timed behavior
// 200ms = 2 ticks at 100ms intervals - documented and justified
```

**Requirements:**
1. First wait for the triggering condition
2. Based on known timing (not guessing)
3. Comment explaining WHY

## Session Note **[EXAMPLE]**

From a debugging session (2025-10-03): arbitrary timeouts replaced with condition waiting in 15 flaky tests across 3 files; that suite went from intermittent to stable. Treat as an anecdote from one codebase, not a promised rate.
