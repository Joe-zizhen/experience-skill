import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

export function fingerprint(root) {
  const hash = crypto.createHash('sha256');
  let count = 0;
  function visit(directory) {
    for (const name of fs.readdirSync(directory).sort()) {
      const file = path.join(directory, name);
      const stat = fs.lstatSync(file);
      if (stat.isSymbolicLink()) throw new Error('Fixture links are unsupported');
      if (stat.isDirectory()) visit(file);
      else {
        hash.update(path.relative(root, file), 'utf8');
        hash.update(fs.readFileSync(file));
        count += 1;
      }
    }
  }
  visit(root);
  return { count, sha256: hash.digest('hex') };
}

export function cachedFixture(t, name) {
  const supplied = process.env.EXPERIENCE_TEST_FIXTURES;
  if (!supplied) return null;
  if (!path.isAbsolute(supplied)) throw new Error('Fixture cache path must be absolute');
  const root = fs.realpathSync(supplied);
  if (!/^budget-fixtures-/.test(path.basename(root)) || path.basename(path.dirname(root)) !== 'reports') throw new Error('Fixture cache must be a generated reports directory');
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json'), 'utf8'));
  if (manifest.schema !== 1 || !manifest.stores[name]) throw new Error('Invalid fixture manifest');
  const store = path.join(root, name);
  const before = fingerprint(store);
  if (JSON.stringify(before) !== JSON.stringify(manifest.stores[name])) throw new Error('Fixture cache drift');
  t.after(() => {
    if (JSON.stringify(fingerprint(store)) !== JSON.stringify(before)) throw new Error('Read-only fixture changed');
  });
  return store;
}
