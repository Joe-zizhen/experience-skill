import base from './stryker.config.mjs';

const reportDir = process.env.EXPERIENCE_MUTATION_REPORT_DIR;
if (!reportDir) throw new Error('EXPERIENCE_MUTATION_REPORT_DIR is required');

export default {
  ...base,
  reporters: ['clear-text', 'json', 'html', 'event-recorder'],
  jsonReporter: { fileName: `${reportDir}/mutation.json` },
  htmlReporter: { fileName: `${reportDir}/index.html` },
  eventReporter: { baseDir: `${reportDir}/events` },
  ignorePatterns: ['reports', '.stryker-tmp-*'],
};
