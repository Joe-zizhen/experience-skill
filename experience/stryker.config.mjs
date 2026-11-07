/** Development-only mutation checks; runtime has no package dependency. */
export default {
  mutate: ['scripts/memory.mjs', 'scripts/inject-experience-index.mjs'],
  testRunner: 'command',
  commandRunner: { command: 'node --test tests/*.test.mjs' },
  coverageAnalysis: 'off',
  concurrency: 4,
  timeoutMS: 5000,
  dryRunTimeoutMinutes: 5,
  reporters: ['clear-text', 'json', 'html'],
  jsonReporter: { fileName: 'reports/mutation/mutation.json' },
  htmlReporter: { fileName: 'reports/mutation/index.html' },
  thresholds: { high: 100, low: 100, break: 100 },
  cleanTempDir: true,
};
