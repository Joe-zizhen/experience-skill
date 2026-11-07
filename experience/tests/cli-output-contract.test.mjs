import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { runCli } from '../scripts/memory.mjs';

const budget = 25600;
const bytes = (result) => Buffer.byteLength(`${JSON.stringify(result, null, 2)}\n`, 'utf8');
const page = (id, title = id, body = '依据：合成资料。') => `---\nid: project-a/${id}\nscope: project:project-a\nstatus: active\n---\n# ${title}\n${body}\n`;

function fixture(t, files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'experience-output-contract-'));
  for (const [name, text] of Object.entries(files)) {
    fs.writeFileSync(path.join(root, name), text, 'utf8');
  }
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

// Map a valid long path namespace onto real short fixture files. The subject's
// read/parse/paging code is unchanged; only OS path names are translated.
function withLongRoot(t, physical, desiredBytes, action) {
  let virtual = path.parse(physical).root;
  const segment = '中'.repeat(60);
  while (Buffer.byteLength(virtual, 'utf8') + 182 <= desiredBytes) virtual = path.join(virtual, segment);
  const remainder = desiredBytes - Buffer.byteLength(virtual, 'utf8') - 1;
  if (remainder > 0) virtual = path.join(virtual, 'a'.repeat(remainder));
  const map = (value) => typeof value === 'string' && (value === virtual || value.startsWith(virtual + path.sep))
    ? physical + value.slice(virtual.length) : value;
  const handles = [];
  for (const name of ['statSync', 'lstatSync', 'openSync', 'opendirSync']) {
    const original = fs[name];
    handles.push(t.mock.method(fs, name, (...args) => original(map(args[0]), ...args.slice(1))));
  }
  const originalRealpath = fs.realpathSync;
  handles.push(t.mock.method(fs, 'realpathSync', (...args) => {
    const real = originalRealpath(map(args[0]), ...args.slice(1));
    return real === physical || real.startsWith(physical + path.sep) ? virtual + real.slice(physical.length) : real;
  }));
  try { return action(virtual); } finally { for (const handle of handles) handle.mock.restore(); }
}

test('CLI explains an authorized root that leaves no output capacity', (t) => {
  const root = fixture(t, { 'topic.md': page('topic') });
  for (const command of ['catalog', 'search', 'validate']) {
    withLongRoot(t, root, 27000, (virtual) => {
      const args = [command, '--root', virtual];
      if (command === 'search') args.push('--query', '依据');
      const answer = runCli(args);
      assert.equal(answer.code, 1);
      assert.match(answer.result.error, /root.*budget/i);
      assert.ok(bytes(answer.result) <= budget);
      if (command === 'validate') assert.equal(answer.result.valid, false);
    });
  }
});

test('validation output fallback preserves the actual error and warning totals', (t) => {
  const root = fixture(t, {
    'topic.md': page('topic', 'Topic', '[missing](missing.txt)\n[external](knowledge:other/unknown)'),
  });
  const answer = withLongRoot(t, root, 27000, (virtual) => runCli(['validate', '--root', virtual]));
  assert.equal(answer.code, 1);
  assert.equal(answer.result.valid, false);
  assert.equal(answer.result.errorsTotal, 1);
  assert.equal(answer.result.warningsTotal, 1);
  assert.ok(bytes(answer.result) <= budget);
});

test('catalog and validation keep warnings visible without changing valid knowledge', (t) => {
  const root = fixture(t, { 'topic.md': page('topic', 'Topic', '[external](knowledge:other/unknown)') });
  const catalogResult = runCli(['catalog', '--root', root]);
  assert.equal(catalogResult.code, 0);
  const validation = runCli(['validate', '--root', root]);
  assert.equal(validation.code, 0);
  assert.equal(validation.result.valid, true);
  assert.equal(validation.result.warningsTotal, 1);
  assert.equal(validation.result.warnings.length, 1);
  assert.match(validation.result.warnings[0], /knowledge reference.*other\/unknown/);
  fs.writeFileSync(path.join(root, 'unknown.md'), '# Unstructured material\n', 'utf8');
  const nextCatalog = runCli(['catalog', '--root', root]);
  assert.equal(nextCatalog.result.warningsTotal, 1);
  assert.equal(nextCatalog.result.warnings.length, 1);
  assert.match(nextCatalog.result.warnings[0], /unknown.*format/i);
});

test('short diagnostics remain intact and are not falsely marked as truncated', (t) => {
  const root = fixture(t, { 'topic.md': page('topic', 'Topic', '[missing](missing.txt)') });
  const validation = runCli(['validate', '--root', root]);
  assert.equal(validation.code, 1);
  assert.equal(validation.result.errors.length, 1);
  assert.equal(validation.result.errorsTruncated, 0);
  assert.equal(validation.result.errorsOmitted, 0);
  assert.doesNotMatch(validation.result.errors[0], /diagnostic truncated/);
  assert.match(validation.result.errors[0], /missing\.txt/);
});

test('large pages return complete entries and a resumable offset across byte pressure', (t) => {
  const root = fixture(t, {
    'a.md': page('a', '中'.repeat(2600)),
    'b.md': page('b', '界'.repeat(2600)),
    'c.md': page('c', '文'.repeat(2600)),
  });
  const ids = [];
  let offset = 0;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const answer = runCli(['catalog', '--root', root, '--limit', '3', '--offset', String(offset)]);
    assert.equal(answer.code, 0);
    assert.ok(bytes(answer.result) <= budget);
    assert.equal(answer.result.oversizedEntries.length, 0);
    ids.push(...answer.result.entries.map((entry) => entry.id));
    if (answer.result.nextOffset === null) break;
    assert.ok(answer.result.nextOffset > offset);
    offset = answer.result.nextOffset;
  }
  assert.deepEqual(ids, ['project-a/a', 'project-a/b', 'project-a/c']);
});

test('oversized entries retain source locations and explain how to continue', (t) => {
  const root = fixture(t, { 'a.md': page('a', '中'.repeat(11000)), 'b.md': page('b', '界'.repeat(11000)) });
  for (const rootBytes of [15000, 25000, 25100, 25200, 25300]) {
    withLongRoot(t, root, rootBytes, (virtual) => {
      const answer = runCli(['catalog', '--root', virtual, '--limit', '2']);
      assert.ok(bytes(answer.result) <= budget);
      if (answer.code !== 0) { assert.match(answer.result.error, /budget/i); return; }
      assert.ok(answer.result.examined > 0, 'successful page must examine or locate at least one pending entry');
      assert.ok(answer.result.oversizedEntries.length > 0);
      for (const omitted of answer.result.oversizedEntries) {
        assert.ok(Number.isInteger(omitted.index));
        assert.match(omitted.reason, /budget/i);
        if (!omitted.file) assert.match(omitted.reason, /offset.*limit 1/i);
      }
      assert.ok(answer.result.nextOffset === null || answer.result.nextOffset > answer.result.offset);
    });
  }
});

test('a page unable to fit even an oversized locator fails visibly rather than looping', (t) => {
  const root = fixture(t, { 'a.md': page('a', '中'.repeat(11000)) });
  for (const rootBytes of [25340, 25360, 25380, 25400, 25420, 25440, 25460, 25500]) {
    withLongRoot(t, root, rootBytes, (virtual) => {
      const answer = runCli(['catalog', '--root', virtual, '--limit', '1']);
      assert.ok(bytes(answer.result) <= budget);
      if (answer.code === 0) {
        assert.ok(answer.result.examined > 0 || answer.result.total === 0, 'success must not return the same pending offset with no explanation');
      } else {
        assert.match(answer.result.error, /budget/i);
      }
    });
  }
});

test('limit-one pages either provide an oversized source locator or a visible budget failure', (t) => {
  const name = 'topic-'.repeat(35) + '.md';
  const root = fixture(t, { [name]: page('topic', '中'.repeat(11000)) });
  for (let rootBytes = 24800; rootBytes <= 25320; rootBytes += 20) {
    withLongRoot(t, root, rootBytes, (virtual) => {
      const answer = runCli(['catalog', '--root', virtual, '--limit', '1']);
      assert.ok(bytes(answer.result) <= budget);
      if (answer.code === 0) {
        assert.equal(answer.result.oversizedEntries.length, 1);
        assert.equal(answer.result.oversizedEntries[0].file, name, 'limit 1 must not promise a locator on another identical limit-1 retry');
      } else {
        assert.match(answer.result.error, /budget/i);
      }
    });
  }
});
