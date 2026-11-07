import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fingerprint } from './budget-fixtures.mjs';

const reports = fileURLToPath(new URL('../../reports/', import.meta.url));
fs.mkdirSync(reports, { recursive: true });
const root = fs.mkdtempSync(path.join(reports, 'budget-fixtures-'));
const topic = (id) => `---\nid: project-a/${id}\nscope: project:project-a\nstatus: active\n---\n# 主题覆盖\n\n适用条件：当前项目\n依据：实际验证\n检索词：颜色 样式\n`;
const write = (store, relative, text) => {
  const file = path.join(root, store, relative);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text, 'utf8');
};
for (const store of ['file-budget', 'depth-budget']) {
  for (let i = 0; i < 257; i += 1) write(store, `entry-${String(i).padStart(3, '0')}.md`, topic(`id-${i}`));
}
write('depth-budget', 'a/b/c/d/e/f/g/h/i/deep.md', topic('deep'));
write('entry-budget', 'topic.md', topic('theme'));
for (let i = 0; i < 4096; i += 1) write('entry-budget', `entry-${i}.txt`, '');
const stores = Object.fromEntries(['file-budget', 'depth-budget', 'entry-budget'].map((name) => [name, fingerprint(path.join(root, name))]));
fs.writeFileSync(path.join(root, 'manifest.json'), `${JSON.stringify({ schema: 1, stores }, null, 2)}\n`, 'utf8');
process.stdout.write(`${root}\n`, 'utf8');
