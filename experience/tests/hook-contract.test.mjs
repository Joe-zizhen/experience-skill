import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { buildOutput, renderCatalog } from '../scripts/inject-experience-index.mjs';

const script = fileURLToPath(new URL('../scripts/inject-experience-index.mjs', import.meta.url));

function layer(name, lengths) {
  return {
    name, root: `/fixture/${name}`, warnings: 0, unavailable: false,
    entries: lengths.map((length, i) => ({ id: `${name}/${i}`, title: 'x'.repeat(length),
      target: `${i}.md`, status: 'active', scope: 'general', legacy: false })),
  };
}

function rows(output) {
  const lines = output.trimEnd().split('\n');
  const first = lines.findIndex((line) => line.startsWith('{"roots":'));
  const last = lines.findIndex((line) => line.startsWith('[目录覆盖] '));
  assert.ok(first >= 0 && last > first);
  return lines.slice(first + 1, last).map((line) => JSON.parse(line));
}

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'experience-hook-contract-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const trusted = path.join(root, 'trusted');
  const outside = path.join(root, 'outside');
  fs.mkdirSync(trusted);
  fs.mkdirSync(outside);
  const allowlist = path.join(root, 'roots.txt');
  fs.writeFileSync(allowlist, `${trusted}\n`, 'utf8');
  return { root, trusted, outside, allowlist, data: path.join(root, 'data') };
}

test('catalog row region contains complete candidate JSON without synthetic blank rows', () => {
  const layers = [layer('project', [40, 50]), layer('general', [40])];
  const output = renderCatalog(layers, 2000);
  const actual = rows(output);
  assert.equal(actual.length, 3);
  assert.deepEqual(new Set(actual.map((row) => row.id)), new Set(['project/0', 'project/1', 'general/0']));
  assert.ok(actual.every((row) => row.target.endsWith('.md')));
  // Pending rows are exercised too: the large first layer cannot consume the second layer's allocation.
  const constrained = renderCatalog([layer('project', [1050]), layer('general', [350])], 2000);
  const selected = rows(constrained);
  assert.deepEqual(selected.map((row) => row.id), ['general/0']);
  assert.ok(Buffer.byteLength(constrained, 'utf8') <= 2000);
});

test('the affordable layer retains its allocation when the first candidate exceeds its share', () => {
  const output = renderCatalog([layer('project', [1050]), layer('general', [350])], 2000);
  assert.deepEqual(rows(output).map((entry) => entry.id), ['general/0']);
  const coverage = JSON.parse(output.split('\n').find((line) => line.startsWith('[目录覆盖] ')).slice('[目录覆盖] '.length));
  assert.deepEqual(coverage.map(({ layer: name, loaded, omitted }) => ({ name, loaded, omitted })), [
    { name: 'project', loaded: 0, omitted: 1 },
    { name: 'general', loaded: 1, omitted: 0 },
  ]);
});

test('buildOutput treats an existing unauthorized root as an empty result without reading stores', (t) => {
  const f = fixture(t);
  const input = Buffer.from(JSON.stringify({ cwd: f.outside }), 'utf8');
  assert.equal(buildOutput(input, ['--allowlist', f.allowlist, '--data-root', f.data]), '');
  assert.equal(fs.existsSync(f.data), false);
});

test('stream input budget rejects excess chunks before stdin is closed', async (t) => {
  const f = fixture(t);
  const child = spawn(process.execPath, [script, '--allowlist', f.allowlist, '--data-root', f.data], {
    env: { ...process.env }, stdio: ['pipe', 'pipe', 'pipe'],
  });
  let stderr = '';
  let stdout = '';
  child.stderr.setEncoding('utf8');
  child.stdout.setEncoding('utf8');
  child.stderr.on('data', (chunk) => { stderr += chunk; });
  child.stdout.on('data', (chunk) => { stdout += chunk; });
  child.stdin.on('error', () => {});
  const closed = new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (code) => resolve(code));
  });
  t.after(() => { if (child.exitCode === null) child.kill(); });
  const chunk = Buffer.alloc(16384, 32);
  for (let i = 0; i < 4; i += 1) child.stdin.write(chunk);
  child.stdin.write(Buffer.from(' ', 'utf8'));
  // Deliberately keep stdin open. A post-EOF parse limit cannot satisfy this resource boundary.
  let timer;
  const deadline = new Promise((resolve) => { timer = setTimeout(() => resolve('deadline'), 4000); });
  const outcome = await Promise.race([closed, deadline]);
  clearTimeout(timer);
  if (outcome === 'deadline') {
    child.kill();
    await closed;
  }
  assert.notEqual(outcome, 'deadline', 'oversized streaming input must terminate without waiting for EOF');
  assert.equal(outcome, 0);
  assert.equal(stdout, '');
  assert.match(stderr, /experience-hook.*skipped/);
});

test('an exact metadata-only budget still exposes roots and omitted coverage', () => {
  const layers = [layer('project', [20])];
  const complete = renderCatalog(layers);
  const candidateLine = complete.split('\n').find((line) => line.startsWith('{"layer":'));
  // The one-digit loaded/omitted counters exchange 1 and 0 without changing their byte lengths.
  const metadataBytes = Buffer.byteLength(complete, 'utf8') - Buffer.byteLength(candidateLine, 'utf8');
  const output = renderCatalog(layers, metadataBytes);
  assert.notEqual(output, '');
  assert.equal(Buffer.byteLength(output, 'utf8'), metadataBytes);
  assert.match(output, /"loaded":0,"omitted":1/);
  assert.equal(renderCatalog(layers, metadataBytes - 1), '');
});

test('a layer whose candidate exactly fits its share is not displaced by another project row', () => {
  const output = renderCatalog([layer('project', [100, 100]), layer('general', [200])], 1355);
  const selected = rows(output).map((row) => row.id).sort();
  assert.deepEqual(selected, ['general/0', 'project/0']);
  assert.ok(Buffer.byteLength(output, 'utf8') <= 1355);
});

test('many small project entries cannot crowd out an affordable general entry', () => {
  const output = renderCatalog([layer('project', Array(10).fill(0)), layer('general', [1000])], 2987);
  const selected = rows(output);
  assert.ok(selected.some((entry) => entry.id === 'general/0'));
  assert.ok(selected.some((entry) => entry.layer === 'project'));
  assert.ok(Buffer.byteLength(output, 'utf8') <= 2987);
});
