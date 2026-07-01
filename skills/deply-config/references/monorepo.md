# Monorepo Guidance

Use this when the repository has multiple Python apps, services, packages, or source roots.

## One Config vs Many

Use one root `deply.yaml` when:

- Services share architecture rules.
- CI should run one architecture check for the whole repo.
- Layers can be named without ambiguity.
- Cross-package dependencies are intentional architecture boundaries.

Use multiple configs when:

- Services have different frameworks or architecture styles.
- One service is legacy and another is strict.
- Teams own separate packages and CI runs per package.
- Layer names would need prefixes everywhere to stay clear.

Default to one root config for v1 unless separate services clearly need different rules.

## Paths

Root config example:

```yaml
deply:
  paths:
    - "apps/api"
    - "packages/core"
    - "services/worker"
```

Per-service config example:

```yaml
deply:
  paths:
    - "."
```

Run per-service configs from the service root, or pass an explicit config path from repo root.

## Layer Naming

For one root config, use unambiguous names:

- `api_interface`
- `api_application`
- `core_domain`
- `worker_tasks`
- `shared_infrastructure`

For per-service configs, short names are fine:

- `domain`
- `application`
- `infrastructure`
- `interface`

## Common Layouts

`apps/*`:

```yaml
- name: api_interface
  collectors:
    - type: directory
      directories:
        - "apps/api/src/api"
```

`services/*`:

```yaml
- name: worker_tasks
  collectors:
    - type: directory
      directories:
        - "services/worker/src/tasks"
```

`packages/*`:

```yaml
- name: core_domain
  collectors:
    - type: directory
      directories:
        - "packages/core/src/core/domain"
```

`src/*`:

```yaml
- name: domain
  collectors:
    - type: directory
      directories:
        - "src/project/domain"
```

## Rules

Root configs should model cross-package boundaries explicitly:

```yaml
ruleset:
  core_domain:
    disallow_layer_dependencies:
      - api_interface
      - shared_infrastructure
```

Per-service configs should stay service-local and avoid pretending to protect unrelated packages.
