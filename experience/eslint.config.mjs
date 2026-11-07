// These guards implement the approved read-only, standard-library architecture.
const allowedImports = '^(?!(?:node:(?:fs|path|os|url|util|buffer|process)|\\./memory\\.mjs)$).+';
const writes = 'writeFile|writeFileSync|appendFile|appendFileSync|write|writeSync|mkdir|mkdirSync|mkdtemp|mkdtempSync|rm|rmSync|rmdir|rmdirSync|unlink|unlinkSync|rename|renameSync|copyFile|copyFileSync|cp|cpSync|truncate|truncateSync|ftruncate|ftruncateSync|createWriteStream|symlink|symlinkSync|link|linkSync|chmod|chmodSync|chown|chownSync|utimes|utimesSync';

export default [
  {
    ignores: ['node_modules/**', '.stryker-tmp/**', 'reports/**'],
  },
  {
    files: ['scripts/*.mjs'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: {
        Buffer: 'readonly',
        console: 'readonly',
        process: 'readonly',
        TextDecoder: 'readonly',
        URL: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
      },
    },
    rules: {
      complexity: ['error', 10],
      'no-undef': 'error',
      'no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-constant-condition': 'error',
      'no-eval': 'error',
      'no-new-func': 'error',
      'no-restricted-globals': ['error', 'fetch', 'WebSocket', 'XMLHttpRequest'],
      'no-restricted-imports': ['error', {
        patterns: [{ regex: allowedImports, message: 'Runtime uses only approved Node read-only modules and the memory helper.' }],
        paths: [{ name: 'node:fs', importNames: writes.split('|').concat(['open', 'openSync']), message: 'Runtime helpers do not write files.' }],
      }],
      'no-restricted-syntax': [
        'error',
        { selector: 'ImportExpression', message: 'Dynamic imports bypass the explicit runtime dependency boundary.' },
        { selector: "CallExpression[callee.name='require']", message: 'Use static standard-library imports.' },
        { selector: "CallExpression[callee.object.name='process'][callee.property.name=/^(binding|dlopen)$/]", message: 'Native bindings bypass the read-only boundary.' },
        { selector: "MemberExpression[property.name=/^(fetch|WebSocket|XMLHttpRequest)$/]", message: 'Runtime helpers do not access the network.' },
        { selector: `MemberExpression[object.name='fs'][property.name=/^(${writes})$/]`, message: 'Runtime helpers do not write files.' },
        { selector: `ImportDeclaration[source.value='node:fs'] ImportSpecifier[imported.name=/^(${writes})$/]`, message: 'Runtime helpers do not import write capabilities.' },
        { selector: "ImportDeclaration[source.value='node:fs'] ImportDefaultSpecifier[local.name!='fs']", message: 'Keep the fs namespace explicit so read-only guards stay effective.' },
        { selector: "ImportDeclaration[source.value='node:fs'] ImportNamespaceSpecifier[local.name!='fs']", message: 'Keep the fs namespace explicit so read-only guards stay effective.' },
        { selector: "MemberExpression[object.name='fs'][computed=true]", message: 'Use explicit fs methods so the capability boundary can be checked.' },
        { selector: "CallExpression[callee.object.name='fs'][callee.property.name=/^(open|openSync)$/]:not([arguments.1.value='r'])", message: 'File handles are opened in explicit read-only mode.' },
        { selector: `VariableDeclarator[init.name='fs'] Property[key.name=/^(${writes})$/]`, message: 'Runtime helpers do not extract file-writing capabilities.' },
      ],
    },
  },
  {
    files: ['scripts/memory.mjs'],
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [{ regex: '^(?!node:(?:fs|path|os|url|util|buffer|process)$).+', message: 'The memory helper is a leaf module and does not import the hook or third-party modules.' }],
        paths: [{ name: 'node:fs', importNames: writes.split('|').concat(['open', 'openSync']), message: 'Runtime helpers do not write files.' }],
      }],
    },
  },
];
