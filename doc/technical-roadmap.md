---
layout: default
title: Technical Roadmap
nav_order: 10
---

# Technical Roadmap

This roadmap prioritizes correctness before adoption and performance work. The
assessment reflects the codebase on 2026-10-02.

## Priority order

### P0: eliminate incorrect green results

1. **Harden validation, then require it for every analysis — resolved.**
   `ConfigValidator` rejects missing or file-valued analysis paths, unknown
   collector fields, and invalid `element_type` values. `deply analyze` runs the
   same validation before creating the runner and exits with status `1` when the
   configuration is invalid.

2. **Support async and nested scopes correctly — resolved.** `DependencyVisitor`
   now routes `FunctionDef` and `AsyncFunctionDef` through shared handling and
   restores the previous code element after nested functions and classes. Top-level
   async dependencies use their own element, while uncollected nested scopes remain
   unattributed instead of leaking into their parent.

3. **Replace global name matching with module-aware resolution — core slice
   completed.** An internal module and lexical-binding index resolves absolute and
   relative imports, aliases, and explicit `__init__.py` re-exports through included
   files, including files without collected elements. Duplicate names in unrelated
   modules no longer match. Ambiguous internal module paths fail analysis rather
   than choosing a target. Lookup handles parameters, local assignments, nested
   functions, comprehensions, and class-versus-method scopes. Known attribute
   prefixes such as `models.Project` resolve to the collected class in
   `models.Project.objects.all()` without runtime type inference.

   **Preserved ownership.** Internal import edges inside a
   function, async function, method, or class belong only to the nearest enclosing
   definition when it is collected. Uncollected nested definitions no longer leak
   their imports to other elements. Module-level imports retain file-wide
   propagation; collected module-level assignments own dependencies in their values.
   Existing v1 YAML, collectors, rules, dependency payloads, and reports remain
   supported. Scan paths provide module roots through regular packages, conventional
   `src` layouts, and relative namespace directories without a new config schema.

   **Pending: advanced resolution and completeness.** General control-flow analysis,
   wildcard imports, and dynamic instance types remain unsupported. Conditional
   bindings are conservatively unresolved, while syntactic import edges remain
   checked. Unresolved references must not create guessed links; import edges
   remain the reliable core, and attribute-prefix detection does not prove dynamic
   call targets.

4. **Define one explicit layer-ownership contract — resolved.** An element belongs
   to every layer whose collector matches it. Dependency checks evaluate every
   unique source and target membership pair except equal layer names, and external
   import checks apply to every membership. Collector and layer order has no
   precedence. Raw dependency metrics still count each code dependency once, while
   multiple explicitly forbidden membership pairs may produce multiple violations.
   The bundled DDD recipe uses context and domain memberships as separate axes
   without duplicate cross-context rules.

5. **Fail on incomplete analysis — resolved.** Collection and dependency-analysis
   read or parse failures are reported and make analysis fail. Analysis also fails
   when no Python files are found, no elements map to configured layers, or imports
   resolve to ambiguous internal modules.

6. **Report measurable analysis completeness — resolved.** Reports expose unique
   discovered, excluded, included, parsed, mapped, and unmapped files; mapped and
   overlapping elements; and raw detected dependencies. Incomplete analysis emits
   the available metrics with its errors. These counters reuse existing analysis
   passes. Unresolved references and stable violation fingerprints remain pending
   until their resolution semantics and public violation identities are defined.

### P1: improve adoption after correctness

7. **Add an exact violation baseline.** `--max-violations` permits a new violation
   when another one disappears, while inline ignores modify source. A generated
   baseline should fingerprint rule ID, normalized relative path, stable source and
   target identities, and architecture context. Location belongs in the stored
   diagnostic, not the primary fingerprint, because unrelated line movement must
   not invalidate the baseline. Suppress only existing fingerprints and fail on new
   ones. Implement this after violation identities and dependency resolution are
   stable to avoid baseline churn.

8. **Add opt-in cycle detection.** Strongly connected components after projecting
   resolved dependencies onto the layer graph are useful, but a cycle is not
   universally forbidden. Expose a rule rather than an unconditional check and
   report the shortest actionable cycle. Define how unresolved and heuristic edges
   affect the graph first; cycles must not amplify inference errors.

### P2: improve integrations

9. **Add SARIF 2.1.0 output — resolved.** `--report-format=sarif` exports stable
   rule IDs, line-level source locations, messages, help links, and completeness
   metrics without a new dependency. Results use a fixed `warning` level.
   Existing GitHub Actions annotations remain available. See the CLI guide for
   GitHub upload instructions; GitLab integration is not verified.

10. **Optimize only after measuring.** Collection parses each file once, and
    `CodeAnalyzer` parses included files again to index imports and re-exports.
    External-import checks reuse imports
    extracted during collection when configured, so they no longer add a third
    parse. `--parallel` still covers only collection. Benchmark representative
    repositories after the resolver redesign, then optimize only the measured
    bottleneck.

### Immediate documentation maintenance

11. **Keep public claims verifiable — resolved.** Package, Agent Skill, and
    documentation versions are aligned. Public badges use live PyPI and CI data.
    Documentation distinguishes direct absolute-import checks from heuristic
    internal symbol inference and describes recipes as editable examples rather
    than built-in CLI presets.

### P3: defer until demand is demonstrated

12. **Prefer scriptable presets over an interactive `deply init` wizard.** The 21
    architecture recipes are documentation, not versioned built-in CLI presets.
    The Agent Skill's `light`, `medium`, and `strict` profiles are guidance, not
    runtime features. If setup friction is demonstrated, first add a small
    non-interactive command such as
    `deply init --preset fastapi` with validated packaged templates and safe
    overwrite behavior. Add a wizard only if users still need one.

13. **Defer custom rule plugins.** Custom collectors already load user Python code,
    but rule interfaces may change with layer ownership and dependency resolution.
    Stabilize those contracts first. If real users need plugins afterward, mirror
    the existing `BaseCollector` pattern with a validated `BaseRule` subclass rather
    than introducing a second function-based plugin protocol.

## Assessment of proposed recommendations

| # | Recommendation | Verdict | Priority | Reason |
|---|---|---|---|---|
| 1 | Map an element to `Set[str]` | Resolved with explicit pair evaluation | P0 | Every matching membership is preserved and each unique source-target pair is checked independently of collector order. |
| 2 | Violation baseline | Valid and worth doing | P1 | Enables incremental adoption more safely than `--max-violations`; depends on stable violation identity. |
| 3 | Layer cycle detection | Valid as an opt-in rule | P1 | Useful after graph correctness; not every architecture forbids every cycle. |
| 4 | Parallel dependency analysis | Performance concern valid; action unproven | P2 | Collection and resolution parse included files separately; profiling must justify changes. |
| 5 | Improve name resolution | Core module/import/lexical slice completed | P0 | Module identities, aliases, relative imports, re-exports, and basic shadowing resolve statically; advanced control flow and dynamic types remain pending. |
| 6 | SARIF report | Resolved | P2 | SARIF 2.1.0 output and GitHub upload recipe; analysis accuracy limitations remain. |
| 7 | `deply init` | Direction valid; wizard premature | P3 | Recipes are not packaged presets and the agent skill already reduces setup cost. Start with a scriptable preset only after measuring demand. |
| 8 | Custom rule plugins | Technically valid; defer | P3 | No demonstrated demand and core rule contracts are not stable enough yet. |

## Verified evidence

Before the scoped async/nested-scope fix, probes reproduced these failure modes:

```text
sync function dependency: detected
async function dependency: missed
aliased import dependency: missed
two equal target names: dependencies emitted to both targets
call after nested function: missed
invalid path before validation preflight: `deply validate` exit 1; `deply analyze` exit 0 with 0 violations
```

The module-aware resolver addresses the aliased-import and equal-name cases above.
Focused regression coverage also exercises relative imports, package re-exports,
lexical shadowing, source ownership, and the `models.Project.objects.all()` case
with existing YAML configuration.

Relevant implementation points:

- `deply/main.py`: explicit validation and analysis use the same validation preflight.
- `deply/deply_runner.py`: incomplete collection fails analysis; layer ownership
  preserves every matching layer and evaluates membership pairs; only collection
  uses the process pool.
- `deply/code_analyzer.py`: included files are read and parsed again; failures and
  ambiguous-module diagnostics are returned to the runner.
- `deply/utils/module_resolver.py`: module identities, import bindings, re-exports,
  and lexical scopes resolve internal targets without global short-name matching.
- `deply/utils/dependency_visitor.py`: async and sync functions share recursive
  scope handling; definitions and collected assignments own dependency events.
- `deply/reports/formats/json_report.py`: reports expose violations and additive
  analysis completeness metrics.

## Delivery sequence

Each item should be a separate change with focused regression tests:

1. ~~Harden configuration validation.~~ Resolved.
2. ~~Require validation before analysis.~~ Resolved.
3. ~~Fail on incomplete analysis.~~ Resolved.
4. ~~Fix async and nested-scope correctness.~~ Resolved.
5. ~~Define layer ownership and overlap semantics.~~ Resolved.
6. ~~Build the core module/import/lexical resolver.~~ Completed; advanced
   control-flow and dynamic resolution remain deferred.
7. ~~Add completeness metrics.~~ Resolved independently of the resolver.
8. Add stable violation fingerprints after stable module identities.
9. Add baseline support.
10. Add the opt-in cycle rule.
11. ~~Add SARIF output.~~ Resolved independently of the resolver.
12. Optimize only with before/after benchmarks.
