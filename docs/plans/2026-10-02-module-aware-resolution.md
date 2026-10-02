# Module-aware dependency resolution

Status: implemented and verified on `fix/module-aware-resolver`.
Base: `origin/main` at `d33ccc0`.

## Contract

- Resolve dependencies through module identity, imports and lexical bindings,
  without matching unrelated symbols by their unqualified name.
- Detect `from . import models` followed by `models.Project.objects.all()` by
  resolving the known `Project` prefix; no Django runtime or type inference.
- Preserve v1 YAML, collector matching, `CodeElement`, `Dependency`, reports,
  layer membership pairs, suppression and CLI exit-code contracts.
- Preserve file-wide module-import propagation and nearest-definition local
  import ownership, including uncollected nested definitions.
- Index included files without collected elements for package re-exports.
- Do not execute imports. Ambiguous and dynamic targets must not create guessed
  links. Do not implement general control-flow or instance-type analysis.

## Steps

1. Add integration regressions for module targets, aliases, relative imports,
   package re-exports, duplicate names, known attribute prefixes and shadowing.
2. Build one internal module/symbol resolver from the included ASTs. Infer
   regular-package and scan-directory roots, including conventional `src` roots;
   keep duplicate module candidates ambiguous.
3. Route all visitor target lookups through the resolver. Keep explicit target
   maps supported for callers that supply a context-free visitor directly.
4. Pass included files and analysis paths from the runner; preserve all existing
   rule, ownership and reporting behavior. Correct invalid import test fixtures
   while retaining their original ownership and violation assertions.
5. Document resolution and static boundaries; run focused tests, `make check`,
   review the complete scoped diff independently and fix in-scope findings.

## Verification

- Baseline: 181 tests passed before changes.
- Added 30 integration regressions covering the issue, import identity, lexical
  scopes, package boundaries, re-exports, ambiguity, and existing v1 YAML.
- Corrected invalid import paths in legacy fixtures while preserving their
  original dependency ownership and violation assertions.
- `make check` passed: Ruff, mypy, dependency audit, and all 211 tests on Python 3.14.
- All 211 tests passed on Python 3.8; one Python 3.12+ generic-syntax test skipped.
- CI coverage gates passed: 96.14% line coverage and 90.61% branch coverage.
- Independent review approved the scoped diff after regression fixes;
  `git diff --check` passed.
