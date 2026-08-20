// Tests for condition-based-waiting-example.ts (node:test, no external deps).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { waitFor } from './condition-based-waiting-example';

test('resolves when condition becomes true', async () => {
  let n = 0;
  const r = await waitFor(() => (++n >= 3 ? n : undefined), 'n>=3', { intervalMs: 1 });
  assert.equal(r, 3);
});

test('rejects on timeout', async () => {
  await assert.rejects(
    () => waitFor(() => undefined, 'never', { timeoutMs: 30, intervalMs: 5 }),
    /Timeout waiting for never/
  );
});

test('sync predicate throw rejects the promise', async () => {
  await assert.rejects(
    () =>
      waitFor(() => {
        throw new Error('boom');
      }, 'throwing'),
    /threw: boom/
  );
});

test('async predicate rejection rejects the promise', async () => {
  await assert.rejects(
    () => waitFor(async () => Promise.reject(new Error('async boom')), 'async throwing'),
    /threw: async boom/
  );
});

test('abort signal cancels the wait', async () => {
  const ac = new AbortController();
  setTimeout(() => ac.abort(), 10);
  await assert.rejects(
    () => waitFor(() => undefined, 'aborted wait', { signal: ac.signal, intervalMs: 5 }),
    /Aborted while waiting/
  );
});
