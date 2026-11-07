#!/usr/bin/env node
// Read-only local memory inspection. No network, persistence, or command execution.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { TextDecoder } from 'node:util';

const MAX_FILE_BYTES = 1024 * 1024;
const MAX_STORE_BYTES = 8 * MAX_FILE_BYTES;
const MAX_FILES = 256;
const MAX_DEPTH = 8;
const MAX_DIRECTORY_ENTRIES = 4096;
// Derived metadata needs its own bounds: a small index can fan out over many cards.
const MAX_RECORDS = 512;
const MAX_INDEX_ROUTES = 512;
const MAX_ALIASES = 8;
const MAX_ALIAS_BYTES = 1024;
const MAX_ROUTE_TARGET_BYTES = 4096;
const MAX_REFERENCES = 2048;
const MAX_CLI_BYTES = 25600;
const LEGACY = new Set(['general.md', 'pitfalls.md', 'project.md', 'code.md', 'archive.md']);
const STATUSES = new Set(['active', 'needs-review', 'retired']);
const ID = /^[a-z0-9][a-z0-9._-]*(?:\/[a-z0-9][a-z0-9._-]*)+$/;
const SCOPE = /^(?:general|(?:project|machine):[a-z0-9][a-z0-9._-]*)$/;

function inside(root, candidate) {
  const relative = path.relative(root, candidate);
  return relative === '' || (!relative.startsWith(`..${path.sep}`) && relative !== '..' && !path.isAbsolute(relative));
}

function decode(bytes) {
  if (bytes.length >= 3 && bytes[0] === 239 && bytes[1] === 187 && bytes[2] === 191) throw new Error('UTF-8 BOM is not supported');
  const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
  if (text.includes(String.fromCharCode(0xfffd))) throw new Error('UTF-8 replacement character is not supported');
  return text;
}

function boundedRead(file, maxBytes, guard = () => {}) {
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 0 || maxBytes > MAX_STORE_BYTES) throw new Error('Invalid read budget');
  const fd = fs.openSync(file, 'r');
  try {
    const stat = fs.fstatSync(fd);
    if (!stat.isFile()) throw new Error('Not a regular file');
    if (stat.size > maxBytes) throw new Error('File exceeds read budget');
    guard(stat);
    const buffer = Buffer.alloc(maxBytes + 1);
    let used = 0;
    let count;
    do {
      count = fs.readSync(fd, buffer, used, buffer.length - used, null);
      used += count;
    } while (count > 0 && used < buffer.length);
    if (used > maxBytes) throw new Error('File exceeds read budget');
    return decode(buffer.subarray(0, used));
  } finally {
    fs.closeSync(fd);
  }
}

export function readUtf8(file, maxBytes = MAX_FILE_BYTES) {
  return boundedRead(file, maxBytes);
}

function realRoot(root) {
  if (typeof root !== 'string' || !root.trim()) throw new Error('An explicit root is required');
  const resolved = fs.realpathSync(root);
  if (!fs.statSync(resolved).isDirectory()) throw new Error('Root is not a directory');
  return resolved;
}

function checkedPath(root, candidate) {
  const lexical = path.resolve(candidate);
  if (!inside(root, lexical)) throw new Error('Path escapes knowledge root');
  let current = root;
  for (const part of path.relative(root, lexical).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    if (fs.lstatSync(current).isSymbolicLink()) throw new Error('Symbolic links and junctions are not followed');
  }
  const real = fs.realpathSync(lexical);
  if (!inside(root, real)) throw new Error('Resolved path escapes knowledge root');
  return real;
}

function checkedRead(root, file, budget) {
  const safe = checkedPath(root, file);
  const expected = fs.statSync(safe);
  return boundedRead(safe, budget, (actual) => {
    if (expected.dev !== actual.dev || expected.ino !== actual.ino) throw new Error('File changed before read');
    checkedPath(root, safe);
  });
}

export function readCheckedUtf8(root, file, maxBytes = MAX_FILE_BYTES) {
  return checkedRead(root, file, maxBytes);
}

function directoryEntries(dir, limit) {
  const handle = fs.opendirSync(dir);
  const entries = [];
  try {
    let item;
    while ((item = handle.readSync()) !== null) {
      if (entries.length === limit) return { entries, limited: true };
      entries.push(item);
    }
    return { entries, limited: false };
  } finally { handle.closeSync(); }
}

function collectEntry(root, dir, item, state, depth, visit) {
  if (item.name.startsWith('.')) return;
  const full = path.join(dir, item.name);
  if (item.isSymbolicLink()) { state.warnings.push(`Link skipped: ${path.relative(root, full)}`); return; }
  if (item.isDirectory()) { visit(full, depth + 1); return; }
  if (item.isFile() && item.name.toLowerCase().endsWith('.md')) state.files.push(full);
}

function markdownFiles(root, warnings, incomplete) {
  const state = { files: [], warnings, incomplete, remaining: MAX_DIRECTORY_ENTRIES };
  const visit = (dir, depth) => {
    if (depth > MAX_DEPTH) { markIncomplete(state, 'directory-depth', 'Directory depth budget reached; catalog is incomplete'); return; }
    const batch = directoryEntries(dir, state.remaining);
    state.remaining -= batch.entries.length;
    if (batch.limited) markIncomplete(state, 'directory-entries', 'Directory entry budget reached; catalog is incomplete');
    for (const item of batch.entries.sort((a, b) => a.name.localeCompare(b.name))) {
      if (state.files.length === MAX_FILES) { markIncomplete(state, 'files', 'File budget reached; catalog is incomplete'); return; }
      collectEntry(root, dir, item, state, depth, visit);
    }
  };
  visit(root, 0);
  return state.files;
}

function visibleLines(text) {
  let fence = '';
  return text.split(/\r?\n/).map((line) => {
    const marker = line.match(/^\s*(`{3,}|~{3,})(.*)$/);
    if (!fence && marker) { fence = marker[1]; return ''; }
    if (!fence) return line;
    if (marker && marker[1][0] === fence[0] && marker[1].length >= fence.length && !marker[2].trim()) fence = '';
    return '';
  });
}

function slug(text) {
  return text.toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, '').trim().replace(/\s+/g, '-');
}

function scalar(value) {
  const clean = value.trim();
  if (clean.startsWith('"')) {
    const parsed = JSON.parse(clean);
    if (typeof parsed !== 'string') throw new Error('Metadata must contain string scalars');
    return parsed;
  }
  if (clean.startsWith("'")) {
    if (!clean.endsWith("'")) throw new Error('Unclosed metadata string');
    return clean.slice(1, -1).replace(/''/g, "'");
  }
  if (/^[>|\[{]/.test(clean)) throw new Error('Only flat scalar metadata is supported');
  return clean.replace(/\s+#.*$/, '').trim();
}

function metadataFields(lines) {
  const result = {};
  for (const line of lines) {
    if (!line.trim() || line.trim().startsWith('#')) continue;
    const match = line.match(/^([a-z][a-z0-9_-]*):\s*(.*)$/);
    if (!match || Object.hasOwn(result, match[1])) throw new Error('Invalid or duplicate metadata key');
    result[match[1]] = scalar(match[2]);
  }
  return result;
}

function metadata(text) {
  if (!/^---\r?\n/.test(text)) return null;
  const lines = text.split(/\r?\n/);
  const end = lines.indexOf('---', 1);
  if (end < 1 || end > 32) throw new Error('Invalid metadata boundary');
  const result = metadataFields(lines.slice(1, end));
  if (!ID.test(result.id || '')) throw new Error('Invalid or missing id');
  if (!SCOPE.test(result.scope || '')) throw new Error('Invalid or missing scope');
  if (!STATUSES.has(result.status)) throw new Error('Invalid or missing status');
  return { ...result, body: lines.slice(end + 1).join('\n') };
}

function uniqueAnchor(base, counts, used) {
  let suffix = counts.get(base) || 0;
  let anchor = base + (suffix ? `-${suffix}` : '');
  while (used.has(anchor)) {
    suffix += 1;
    anchor = `${base}-${suffix}`;
  }
  counts.set(base, suffix + 1);
  used.add(anchor);
  return anchor;
}

function headings(text) {
  const counts = new Map();
  const used = new Set();
  return visibleLines(text).flatMap((line, lineIndex) => {
    const match = line.match(/^(#{1,6})\s+(.+?)\s*#*$/);
    if (!match) return [];
    return [{ depth: match[1].length, title: match[2], anchor: uniqueAnchor(slug(match[2]), counts, used), lineIndex }];
  });
}

function warnOnce(warnings, message) {
  if (!warnings.includes(message)) warnings.push(message);
}

function markIncomplete(state, reason, message) {
  state.incomplete.add(reason);
  warnOnce(state.warnings, message);
}

function newRecord(relative, meta) {
  const title = headings(meta.body).find((heading) => heading.depth === 1)?.title;
  if (!title) throw new Error('Topic requires a level-one title');
  return { id: meta.id, scope: meta.scope, status: meta.status, title, target: relative, legacy: false, body: meta.body };
}

function legacyRecords(relative, text, scope, limit, state) {
  const lines = text.split(/\r?\n/);
  const sections = headings(text).filter((heading) => heading.depth === 2);
  if (sections.length > limit) markIncomplete(state, 'records', `Record budget ${MAX_RECORDS} reached; catalog is incomplete`);
  return sections.slice(0, limit).map(({ lineIndex, title, anchor }, index) => {
    const body = lines.slice(lineIndex, sections[index + 1]?.lineIndex).join('\n');
    return { id: `legacy:${relative}#${anchor}`, scope: scope || 'legacy', status: path.basename(relative) === 'archive.md' ? 'retired' : 'needs-review', title, target: `${relative}#${anchor}`, legacy: true, body };
  });
}

function parseIndexLine(line) {
  if (!/^\s*[-*]\s+/.test(line)) return null;
  const markdown = line.match(/^\s*[-*]\s+\[([^\]]+)\]\(([^\s)]+)\)(.*)$/);
  if (markdown) return { target: markdown[2], label: `${markdown[1]} ${markdown[3]}`.trim() };
  const arrow = line.match(/^\s*[-*]\s+(.+?)\s*→\s*`?([^\s`「]+\.md)`?(?:\s*「([^」]+)」)?/);
  if (!arrow) return null;
  return { target: arrow[2] + (arrow[3] ? `#${slug(arrow[3])}` : ''), label: arrow[1].trim() };
}

function* indexRoutes(text) {
  for (const line of visibleLines(text)) {
    const entry = parseIndexLine(line);
    if (entry) yield entry;
  }
}

function usableRoute(entry, warnings) {
  if (Buffer.byteLength(entry.label, 'utf8') > MAX_ALIAS_BYTES || Buffer.byteLength(entry.target, 'utf8') > MAX_ROUTE_TARGET_BYTES) {
    warnOnce(warnings, 'Index route byte budget reached; oversized alias or target omitted');
    return false;
  }
  return true;
}

function collectIndexRoutes(state) {
  const routes = [];
  const seen = new Set();
  for (const [source, text] of state.documents) {
    if (path.basename(source) !== 'INDEX.md') continue;
    for (const entry of indexRoutes(text)) {
      if (!usableRoute(entry, state.warnings)) continue;
      const key = JSON.stringify([source, entry.target, entry.label]);
      if (seen.has(key)) continue;
      if (routes.length === MAX_INDEX_ROUTES) {
        warnOnce(state.warnings, `Index route budget ${MAX_INDEX_ROUTES} reached; aliases are incomplete`);
        return routes;
      }
      seen.add(key);
      routes.push({ source, ...entry });
    }
  }
  return routes;
}

function routeTarget(root, source, target) {
  if (target.startsWith('knowledge:')) return { id: target.slice(10) };
  const decoded = decodeURIComponent(target);
  const [name, ...fragment] = decoded.split('#');
  const file = path.resolve(root, path.dirname(source), name || path.basename(source));
  if (!inside(root, file)) return null;
  const relative = path.relative(root, file).split(path.sep).join('/');
  return { path: relative, anchor: fragment.join('#') };
}

function matchesRoute(record, route) {
  if (route.id) return record.id === route.id;
  const [name, ...fragment] = record.target.split('#');
  return name === route.path && (!record.legacy || !route.anchor || fragment.join('#') === route.anchor);
}

function routeExists(route, state) {
  if (!route) return false;
  if (route.id || !route.anchor) return true;
  const text = state.documents.get(route.path);
  return text !== undefined && headings(text).some((heading) => heading.anchor === route.anchor);
}

function addAlias(record, label, warnings) {
  const aliases = record.indexAliases || [];
  if (aliases.includes(label)) return;
  const combined = [...aliases, label].join(' ');
  if (aliases.length === MAX_ALIASES || Buffer.byteLength(combined, 'utf8') > MAX_ALIAS_BYTES) {
    warnOnce(warnings, `Alias budget reached for ${record.target}; additional aliases omitted`);
    return;
  }
  record.indexAliases = [...aliases, label];
  record.indexTerms = combined;
}

function applyIndexTerms(state) {
  for (const entry of state.indexRoutes) {
    try {
      const route = routeTarget(state.root, entry.source, entry.target);
      const matching = routeExists(route, state) ? state.records.filter((record) => matchesRoute(record, route)) : [];
      if (!matching.length) state.warnings.push(`${entry.source}: unresolved index route ${entry.target}`);
      for (const record of matching) addAlias(record, entry.label, state.warnings);
    } catch { state.warnings.push(`${entry.source}: invalid index route ${entry.target}`); }
  }
}

function documentRecords(relative, text, scope, state) {
  const remaining = MAX_RECORDS - state.records.length;
  const meta = metadata(text);
  if (meta && remaining > 0) return [newRecord(relative, meta)];
  if (meta) { markIncomplete(state, 'records', `Record budget ${MAX_RECORDS} reached; catalog is incomplete`); return []; }
  if (LEGACY.has(path.basename(relative))) return legacyRecords(relative, text, scope, remaining, state);
  state.warnings.push(`Unknown Markdown format skipped: ${relative}`);
  return [];
}

function documentPriority(file) {
  const name = path.basename(file);
  if (name === 'archive.md') return 2;
  return LEGACY.has(name) ? 1 : 0;
}

function readDocument(root, file, state, scope) {
  const relative = path.relative(root, file).split(path.sep).join('/');
  try {
    const remaining = MAX_STORE_BYTES - state.bytes;
    const text = checkedRead(root, file, Math.min(MAX_FILE_BYTES, remaining));
    state.bytes += Buffer.byteLength(text, 'utf8');
    state.documents.set(relative, text);
    if (path.basename(file) === 'INDEX.md') return;
    state.records.push(...documentRecords(relative, text, scope, state));
  } catch (error) {
    state.errors.push(`${relative}: ${error.message}`);
  }
}

function uniqueRecords(records, errors) {
  const counts = new Map();
  for (const record of records) counts.set(record.id, (counts.get(record.id) || 0) + 1);
  for (const [id, count] of counts) if (count > 1) errors.push(`Duplicate id excluded: ${id}`);
  return records.filter((record) => counts.get(record.id) === 1);
}

function scopeOption(scope) {
  if (scope !== undefined && !SCOPE.test(scope)) throw new Error('Invalid requested scope');
}

function load(root, options) {
  scopeOption(options.scope);
  const resolved = realRoot(root);
  const state = { root: resolved, records: [], documents: new Map(), warnings: [], errors: [], bytes: 0, incomplete: new Set() };
  const files = markdownFiles(resolved, state.warnings, state.incomplete).sort((left, right) => documentPriority(left) - documentPriority(right));
  for (const file of files) readDocument(resolved, file, state, options.scope);
  state.records = uniqueRecords(state.records, state.errors);
  state.indexRoutes = collectIndexRoutes(state);
  applyIndexTerms(state);
  return state;
}

function selected(records, options) {
  return records.filter((record) => (options.history || record.status !== 'retired') && (!options.scope || record.legacy || record.scope === options.scope));
}

function publicEntry(record) {
  const { id, title, target, status, scope, legacy } = record;
  return { id, title, target, status, scope, legacy, ...(record.indexTerms ? { aliases: record.indexTerms } : {}) };
}

export function catalog(root, options = {}) {
  const state = load(root, options);
  return { root: state.root, entries: selected(state.records, options).map(publicEntry), warnings: [...state.warnings, ...state.errors] };
}

function excerpt(body, terms) {
  const lower = body.toLowerCase();
  const locations = terms.map((term) => lower.indexOf(term)).filter((position) => position >= 0);
  const first = locations.length ? Math.min(...locations) : 0;
  const start = Math.max(0, first - 80);
  return body.slice(start, start + 360);
}

export function search(root, query, options = {}) {
  if (typeof query !== 'string' || !query.trim()) throw new Error('A nonempty query is required');
  const terms = [...new Set(query.trim().toLowerCase().split(/\s+/))];
  const state = load(root, options);
  const candidates = selected(state.records, options).map((record) => {
    const text = `${record.title}\n${record.indexTerms || ''}\n${record.body}`.toLowerCase();
    const score = terms.filter((term) => text.includes(term)).length;
    return { record, score };
  });
  const results = candidates.filter((candidate) => candidate.score > 0).sort((a, b) => b.score - a.score || a.record.id.localeCompare(b.record.id));
  return { root: state.root, entries: results.map(({ record, score }) => ({ ...publicEntry(record), score, snippet: excerpt(record.body, terms), usage: record.status === 'active' ? 'verify-before-use' : 'reference-only' })), warnings: [...state.warnings, ...state.errors] };
}

function* links(text) {
  for (const line of visibleLines(text)) {
    for (const match of line.replace(/`[^`]*`/g, ' ').matchAll(/\[[^\]]*\]\(([^\s)]+)\)/g)) yield match[1];
  }
}

function validateKnowledge(target, source, ids, errors, warnings) {
  const id = target.slice('knowledge:'.length);
  if (!ID.test(id)) { errors.push(`${source}: malformed knowledge reference ${id}`); return; }
  if (ids.has(id)) return;
  const local = [...ids].some((known) => known.split('/')[0] === id.split('/')[0]);
  const message = `${source}: unresolved knowledge reference ${id}`;
  (local ? errors : warnings).push(message);
}

function validateExternal(target, source, errors) {
  try {
    const url = new URL(target);
    if (!/^https?:\/\//i.test(target) || !url.hostname) throw new Error('Unsupported URL');
  } catch {
    errors.push(`${source}: unsupported or malformed link ${target}`);
  }
}

function validateLocal(root, target, source, documents, errors) {
  let decoded;
  try { decoded = decodeURIComponent(target); } catch { errors.push(`${source}: malformed link encoding`); return; }
  const hash = decoded.indexOf('#');
  const name = hash < 0 ? decoded : decoded.slice(0, hash);
  const anchor = hash < 0 ? '' : decoded.slice(hash + 1);
  const file = name ? path.resolve(root, path.dirname(source), name) : path.join(root, source);
  if (!inside(root, file)) { errors.push(`${source}: link escapes knowledge root (not followed): ${target}`); return; }
  try { checkedPath(root, file); } catch (error) { errors.push(`${source}: unavailable link ${target}: ${error.message}`); return; }
  const relative = path.relative(root, file).split(path.sep).join('/');
  if (!anchor || !documents.has(relative)) return;
  if (!headings(documents.get(relative)).some((heading) => heading.anchor === anchor)) errors.push(`${source}: missing heading in ${target}`);
}

function* referenceTargets(source, text) {
  const seen = new Set();
  for (const target of links(text)) {
    if (seen.has(target)) continue;
    seen.add(target);
    yield target;
  }
  if (path.basename(source) !== 'INDEX.md') return;
  // Validation reads the raw routes, independently of catalog alias clipping.
  for (const entry of indexRoutes(text)) {
    if (seen.has(entry.target)) continue;
    seen.add(entry.target);
    yield entry.target;
  }
}

function validateReference(target, source, state, ids, errors, warnings) {
  if (target.startsWith('knowledge:')) validateKnowledge(target, source, ids, errors, warnings);
  else if (/^[a-z][a-z0-9+.-]*:/i.test(target)) validateExternal(target, source, errors);
  else validateLocal(state.root, target, source, state.documents, errors);
}

function validateReferences(state, ids, errors, warnings) {
  let count = 0;
  for (const [source, text] of state.documents) {
    for (const target of referenceTargets(source, text)) {
      if (count === MAX_REFERENCES) { errors.push(`Reference budget ${MAX_REFERENCES} reached; validation is incomplete`); return; }
      validateReference(target, source, state, ids, errors, warnings);
      count += 1;
    }
  }
}

export function validate(root, options = {}) {
  const state = load(root, options);
  const errors = [...state.errors];
  if (state.incomplete.size) errors.push(`Validation incomplete: ${[...state.incomplete].join(', ')}`);
  const warnings = [...state.warnings];
  const ids = new Set(state.records.filter((record) => !record.legacy).map((record) => record.id));
  for (const record of state.records) {
    if (options.scope && !record.legacy && record.scope !== options.scope) errors.push(`${record.target}: scope differs from requested scope`);
  }
  validateReferences(state, ids, errors, warnings);
  return { root: state.root, valid: errors.length === 0, topics: state.records.length, errors, warnings };
}

function argumentsFor(argv) {
  const [command, ...rest] = argv;
  if (!['catalog', 'search', 'validate'].includes(command)) throw new Error('Use catalog, search, or validate');
  const args = { command };
  for (let index = 0; index < rest.length; index += 1) {
    const name = rest[index];
    if (name === '--history') { args.history = true; continue; }
    if (!['--root', '--scope', '--query', '--limit', '--offset'].includes(name)) throw new Error(`Unknown option: ${name}`);
    const key = name.slice(2);
    const value = rest[++index];
    if (!value || value.startsWith('--') || Object.hasOwn(args, key)) throw new Error(`Missing or duplicate option: ${name}`);
    args[key] = value;
  }
  if (!args.root) throw new Error('--root is required');
  return paginationArguments(args);
}

function integerOption(value, fallback, name, minimum, maximum) {
  if (value === undefined) return fallback;
  const number = Number(value);
  if (!/^\d+$/.test(value) || !Number.isSafeInteger(number) || number < minimum || number > maximum) throw new Error(`Invalid ${name}`);
  return number;
}

function paginationArguments(args) {
  if (args.command === 'validate') {
    if (args.limit !== undefined || args.offset !== undefined || args.history) throw new Error('Pagination and history apply only to catalog/search');
    return args;
  }
  return { ...args, limit: integerOption(args.limit, 20, '--limit', 1, 50), offset: integerOption(args.offset, 0, '--offset', 0, Number.MAX_SAFE_INTEGER) };
}

function fitsCli(result) {
  return Buffer.byteLength(`${JSON.stringify(result, null, 2)}\n`, 'utf8') <= MAX_CLI_BYTES;
}

function diagnosticPreview(message) {
  const characters = Array.from(String(message));
  return characters.length > 256 ? `${characters.slice(0, 256).join('')}… [diagnostic truncated]` : String(message);
}

function diagnosticFields(kind, messages) {
  return { [kind]: [], [`${kind}Total`]: messages.length, [`${kind}Omitted`]: messages.length, [`${kind}Truncated`]: 0 };
}

function appendDiagnostics(result, kind, messages) {
  for (const message of messages) {
    const preview = diagnosticPreview(message);
    const candidate = { ...result, [kind]: [...result[kind], preview], [`${kind}Omitted`]: result[`${kind}Omitted`] - 1,
      [`${kind}Truncated`]: result[`${kind}Truncated`] + (preview !== message ? 1 : 0) };
    if (!fitsCli(candidate)) break;
    Object.assign(result, candidate);
  }
}

function noteOversized(result, entry, index) {
  const detail = { index, file: entry.target.split('#')[0], reason: 'Entry exceeds output budget; inspect the source file' };
  result.oversizedEntries.push(detail);
  if (fitsCli(result)) return true;
  result.oversizedEntries.pop();
  return false;
}

function fillPage(result, entries, end) {
  let next = result.offset;
  while (next < end) {
    const entry = entries[next];
    if (fitsCli({ ...result, entries: [...result.entries, entry] })) { result.entries.push(entry); next += 1; continue; }
    if (fitsCli({ ...result, entries: [entry], oversizedEntries: [] })) break;
    if (!noteOversized(result, entry, next)) break;
    next += 1;
  }
  result.nextOffset = next < result.total ? next : null;
  result.examined = Math.max(0, next - result.offset);
}

function boundedPage(raw, args) {
  // Reserve the longest final metadata values while fitting complete entries.
  const result = { root: raw.root, entries: [], total: raw.entries.length, offset: args.offset, limit: args.limit,
    nextOffset: null, examined: args.limit, oversizedEntries: [], ...diagnosticFields('warnings', raw.warnings) };
  if (!fitsCli(result)) return { error: 'Root path exceeds output budget; use a shorter authorized path' };
  fillPage(result, raw.entries, Math.min(raw.entries.length, args.offset + args.limit));
  if (result.nextOffset === args.offset) return { error: 'Output budget cannot fit entry metadata; inspect files within the authorized root', offset: args.offset };
  appendDiagnostics(result, 'warnings', raw.warnings);
  return result;
}

function boundedValidation(raw) {
  const result = { root: raw.root, valid: raw.valid, topics: raw.topics,
    ...diagnosticFields('errors', raw.errors), ...diagnosticFields('warnings', raw.warnings) };
  if (!fitsCli(result)) return { error: 'Root path exceeds output budget', valid: false, errorsTotal: raw.errors.length, warningsTotal: raw.warnings.length };
  appendDiagnostics(result, 'errors', raw.errors);
  appendDiagnostics(result, 'warnings', raw.warnings);
  return result;
}

export function runCli(argv) {
  try {
    const args = argumentsFor(argv);
    let result;
    if (args.command === 'search') result = search(args.root, args.query, args);
    else if (args.command === 'validate') result = validate(args.root, args);
    else result = catalog(args.root, args);
    const output = args.command === 'validate' ? boundedValidation(result) : boundedPage(result, args);
    return { code: output.valid === false || output.error ? 1 : 0, result: output };
  } catch (error) {
    return { code: 1, result: { error: diagnosticPreview(error.message) } };
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const { code, result } = runCli(process.argv.slice(2));
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  process.exitCode = code;
}
