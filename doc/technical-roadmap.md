---
layout: default
title: Technical Roadmap
nav_order: 10
---

# Technical Roadmap

This roadmap prioritizes correctness before adoption and performance work. The
assessment reflects the codebase on 2026-08-07.

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

3. **Replace global name matching with module-aware resolution.** The dependency
   index is keyed by unqualified element name. Import aliases are missed and equal
   names in different modules resolve to every matching element. Build stable
   identities from module path and qualified symbol name, then resolve absolute
   imports, relative imports, and aliases against those identities. Track lexical
   scopes, local imports, assignments, and shadowing so an import or name load is
   attributed only to its real source. Represent modules as analysis nodes or define
   explicit propagation from module-level imports to collected elements; lexical
   scope tracking alone cannot supply that ownership. Import edges should remain
   the reliable core; call and attribute inference must be reported as heuristic
   when exact resolution is impossible.

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
   when no Python files are found or no elements map to configured layers.

6. **Report measurable analysis completeness — resolved.** Reports expose unique
   discovered, excluded, included, parsed, mapped, and unmapped files; mapped and
   overlapping elements; and raw detected dependencies. Incomplete analysis emits
   the available metrics with its errors. These counters reuse existing analysis
   passes. Unresolved references and stable violation fingerprints remain pending
   because they require stable module and symbol identities.

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
   report the shortest actionable cycle. Implement it after module-aware resolution;
   running SCC over the current heuristic graph would amplify false positives.

### P2: improve integrations

9. **Add SARIF 2.1.0 output.** This is useful for GitHub Code Scanning and can be
   implemented without a new dependency. Include stable rule IDs, source locations,
   messages, and help links. Emit a fixed `warning` level, matching current GitHub
   Actions output, until severity becomes an explicit violation property. Keep the
   existing annotations for lightweight CI. Do not describe SARIF as a universal
   GitLab format without a separately verified GitLab integration.

10. **Optimize only after measuring.** Files are parsed at least twice: during
   collection and again by `CodeAnalyzer`. External-import checks add a third pass,
   and eager `setdefault` evaluation can repeat it for overlapping file-layer pairs.
   `--parallel` covers only collection. This is real duplicate work, but independently
   parallelizing the old resolver would preserve its correctness problems. Benchmark
   representative repositories after the resolver redesign, then reuse per-file
   analysis results or parallelize only the measured bottleneck.

### Immediate documentation maintenance

11. **Keep public claims verifiable.** Align package, skill, and documentation
    versions; use a live downloads badge or remove the static claim; distinguish
    exact import checks from heuristic symbol inference; describe recipes as
    editable examples rather than built-in presets. These are confirmed factual
    corrections and should not wait for feature demand.

### P3: defer until demand is demonstrated

12. **Prefer scriptable presets over an interactive `deply init` wizard.** The 21
    architecture recipes are documentation, not versioned built-in presets, and do
    not currently define `light`, `medium`, or `strict` variants. If setup friction
    is demonstrated, first add a small non-interactive command such as
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
| 4 | Parallel dependency analysis | Performance concern valid; action unproven | P2 | Files are parsed at least twice, and more with external-import checks; profiling must justify the redesign. |
| 5 | Improve name resolution | Valid and critical | P0 | Aliases are missed and duplicate names produce ambiguous dependencies. This requires module-aware identities, not another name heuristic. |
| 6 | SARIF report | Valid | P2 | Good GitHub Code Scanning integration, but less important than correct findings. |
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

Relevant implementation points:

- `deply/main.py`: explicit validation and analysis use the same validation preflight.
- `deply/deply_runner.py`: incomplete collection fails analysis; layer ownership
  preserves every matching layer and evaluates membership pairs; only collection
  uses the process pool.
- `deply/code_analyzer.py`: files are read and parsed again, failures are returned
  to the runner, and the global index is keyed by element name.
- `deply/utils/dependency_visitor.py`: async and sync functions share recursive
  scope handling; functions and classes restore their enclosing element.
- `deply/reports/formats/json_report.py`: reports expose violations and additive
  analysis completeness metrics.

## Delivery sequence

Each item should be a separate change with focused regression tests:

1. ~~Harden configuration validation.~~ Resolved.
2. ~~Require validation before analysis.~~ Resolved.
3. ~~Fail on incomplete analysis.~~ Resolved.
4. ~~Fix async and nested-scope correctness.~~ Resolved.
5. ~~Define layer ownership and overlap semantics.~~ Resolved.
6. Build the module-aware, scope-aware resolver.
7. ~~Add completeness metrics.~~ Resolved independently of the resolver.
8. Add stable violation fingerprints after stable module identities.
9. Add baseline support.
10. Add the opt-in cycle rule.
11. Add SARIF output.
12. Optimize only with before/after benchmarks.
