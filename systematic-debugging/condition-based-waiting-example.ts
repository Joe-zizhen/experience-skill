// Condition-based waiting utilities (self-contained, hardened).
// Properties: monotonic clock, configurable poll interval, AbortSignal cancellation,
// predicate errors (sync or async) reject the Promise instead of crashing the process.

import { performance } from 'node:perf_hooks';

export interface WaitOptions {
  timeoutMs?: number; // default 5000
  intervalMs?: number; // default 10 — configurable; never hardcode in callers
  signal?: AbortSignal; // cancellation support
}

/**
 * Wait until `condition` returns a truthy value.
 * Preference order: if your source supports event subscription (EventEmitter,
 * Observable, callbacks), subscribe instead of polling — polling is the fallback
 * for query-only APIs.
 */
export async function waitFor<T>(
  condition: () => T | undefined | null | false | Promise<T | undefined | null | false>,
  description: string,
  options: WaitOptions = {}
): Promise<T> {
  const { timeoutMs = 5000, intervalMs = 10, signal } = options;
  const startTime = performance.now(); // monotonic: unaffected by system clock changes

  while (true) {
    if (signal?.aborted) {
      throw new Error(`Aborted while waiting for ${description}`);
    }

    let result: T | undefined | null | false;
    try {
      result = await condition();
    } catch (err) {
      // A throwing predicate is a defect in the caller — surface it, never swallow it.
      throw new Error(`Condition for "${description}" threw: ${(err as Error).message}`);
    }
    if (result) return result;

    if (performance.now() - startTime > timeoutMs) {
      throw new Error(`Timeout waiting for ${description} after ${timeoutMs}ms`);
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
}

/** Minimal query-only event source shape. */
export interface EventQuery<E> {
  getEvents(threadId: string): E[];
}

export function waitForEvent<E extends { type: string }>(
  source: EventQuery<E>,
  threadId: string,
  eventType: E['type'],
  options: WaitOptions = {}
): Promise<E> {
  return waitForEventMatch(
    source,
    threadId,
    (e) => e.type === eventType,
    `${String(eventType)} event`,
    options
  );
}

export function waitForEventCount<E extends { type: string }>(
  source: EventQuery<E>,
  threadId: string,
  eventType: E['type'],
  count: number,
  options: WaitOptions = {}
): Promise<E[]> {
  return waitFor(
    async () => {
      const matching = source.getEvents(threadId).filter((e) => e.type === eventType);
      return matching.length >= count ? matching : undefined;
    },
    `${count} ${String(eventType)} events`,
    options
  );
}

export function waitForEventMatch<E>(
  source: EventQuery<E>,
  threadId: string,
  predicate: (event: E) => boolean | Promise<boolean>,
  description: string,
  options: WaitOptions = {}
): Promise<E> {
  return waitFor(
    async () => {
      for (const e of source.getEvents(threadId)) {
        // Predicate errors (sync or async) propagate into waitFor's try/catch and reject.
        if (await predicate(e)) return e;
      }
      return undefined;
    },
    description,
    options
  );
}

// Usage example from an actual debugging session:
//
// BEFORE (flaky):
//   await new Promise(r => setTimeout(r, 300)); // hope tools start in 300ms
// AFTER (reliable in that suite):
//   await waitForEventCount(threadManager, threadId, 'TOOL_CALL', 2);
