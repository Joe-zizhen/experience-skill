# Defense-in-Depth Validation

## Overview **[DEFAULT]**

When you fix a bug caused by invalid data, adding validation at one place feels sufficient. But that single check can be bypassed by different code paths, refactoring, or mocks.

**Core principle:** place *independent* defenses at the boundaries where they buy real protection — not at every layer data passes through. Indiscriminate layering duplicates checks, hides the contract's owner, and creates guard theater.

## Where Defenses Belong **[DEFAULT]**

Add an independent defense when — and only when — the data crosses one of these boundaries:

1. **Trust boundary** — external input enters the system (API payload, file ingest, CLI args, env vars). Entry validation rejects obviously invalid input here.
2. **Ownership boundary** — data passes into a module/component whose internals another owner (team, future refactor, generated code) may change without telling you. The consumer re-validates the contract it depends on, because it cannot control the producer.
3. **Irreversible-effect entry** — the last checkpoint before an operation you cannot undo (delete, deploy, `git init` in a directory, send, format). Environment/context guards live here.

If a point matches none of the three, duplicating the check there is usually redundancy, not defense.

**Logging and instrumentation are forensic aids, not a validation layer.** A log line stops nothing. Keep debug logging for post-failure analysis, but never count it as a defense.

## The Boundary Layers, Illustrated **[EXAMPLE]**

### Trust boundary: entry validation

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory || workingDirectory.trim() === '') {
    throw new Error('workingDirectory cannot be empty');
  }
  if (!existsSync(workingDirectory)) {
    throw new Error(`workingDirectory does not exist: ${workingDirectory}`);
  }
  if (!statSync(workingDirectory).isDirectory()) {
    throw new Error(`workingDirectory is not a directory: ${workingDirectory}`);
  }
  // ... proceed
}
```

### Ownership boundary: consumer re-validates

```typescript
function initializeWorkspace(projectDir: string, sessionId: string) {
  if (!projectDir) {
    throw new Error('projectDir required for workspace initialization');
  }
  // ... proceed
}
```

### Irreversible-effect entry: environment guard

```typescript
async function gitInit(directory: string) {
  // In tests, refuse git init outside temp directories
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    const tmpDir = normalize(resolve(tmpdir()));

    // Prefix must include the separator: bare startsWith(tmpDir) is bypassed by
    // same-prefix siblings (Temp-evil.startsWith(Temp) === true)
    if (normalized !== tmpDir && !normalized.startsWith(tmpDir + sep)) {
      throw new Error(
        `Refusing git init outside temp dir during tests: ${directory}`
      );
    }
  }
  // ... proceed
}
```

### Forensics (NOT a defense): debug instrumentation

```typescript
async function gitInit(directory: string) {
  const stack = new Error().stack;
  logger.debug('About to git init', {
    directory,
    cwd: process.cwd(),
    stack,
  });
  // ... proceed
}
```

## Applying the Pattern **[DEFAULT]**

When you find a bug:

1. **Trace the data flow** - Where does the bad value originate? Where is it used?
2. **Map the boundaries it crosses** - trust, ownership, irreversible-effect
3. **Add one independent defense per crossed boundary** - each must catch the bug on its own
4. **Test each defense** - try to bypass the entry check, verify the inner one still catches it

## Example from Session **[EXAMPLE]**

Bug: Empty `projectDir` caused `git init` in source code

**Data flow:**
1. Test setup → empty string
2. `Project.create(name, '')`
3. `WorkspaceManager.createWorkspace('')`
4. `git init` runs in `process.cwd()`

**Defenses added:**
- Trust boundary: `Project.create()` validates directory
- Ownership boundary: `WorkspaceManager` validates projectDir not empty
- Irreversible-effect entry: `WorktreeManager` refuses git init outside tmpdir in tests
- Forensics (not a defense): stack trace logging before git init

**Result:** All 1847 tests passed, bug impossible to reproduce

## Key Insight **[DEFAULT]**

Each boundary caught cases the others missed:

- Different code paths bypassed entry validation
- Mocks bypassed business logic checks
- Edge cases on different platforms needed environment guards
- Debug logging identified structural misuse (but stopped nothing by itself)

**Don't stop at one validation point.** Place the next defense at the next *boundary*, not at the next arbitrary layer.
