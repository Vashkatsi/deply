# Architecture Recipes

Use these to choose layer names and dependency direction. They are starting points, not exhaustive configs.

## Layered App

Typical layers:

- `interface`: CLI, HTTP, workers.
- `application`: use cases and orchestration.
- `domain`: business rules and entities.
- `infrastructure`: database, HTTP clients, queues, SDKs.

Direction:

- Interface depends inward.
- Application depends on domain.
- Domain depends on nothing outward.
- Infrastructure is called through application/domain abstractions where the codebase supports that style.

## Hexagonal / Ports And Adapters

Typical layers:

- `domain`: entities, value objects, domain services.
- `application`: use cases and ports.
- `adapters`: persistence, exchange, HTTP, queue, framework adapters.
- `interface`: web, CLI, worker entrypoints.

Direction:

- Domain has no framework, persistence, transport, SDK, or exchange imports.
- Application depends on domain, not concrete adapters.
- Adapters and interface depend inward.

## Django Pragmatic

Typical layers:

- `models`: Django ORM models.
- `views`: views, viewsets, serializers, routes.
- `services`: business/application services.
- `tasks`: Celery tasks.

Direction:

- Views and tasks may depend on services.
- Services should avoid direct view/framework concerns.
- If user wants strict DDD, split `domain` from Django `models`; otherwise treat Django models as persistence/domain hybrid and avoid over-modeling.

## FastAPI Service

Typical layers:

- `interface`: routers, dependencies, request/response DTOs.
- `application`: use cases.
- `domain`: business objects.
- `infrastructure`: database, external clients, queues.

Direction:

- Routers depend on application.
- Application depends on domain.
- Domain should not import FastAPI, Starlette, SQLAlchemy, HTTP clients, or exchange SDKs in strict mode.

## Modular Monolith

Typical layers:

- `billing_domain`, `billing_application`, `billing_infrastructure`.
- `identity_domain`, `identity_application`, `identity_infrastructure`.
- `shared_kernel` only when it already exists and is stable.

Direction:

- Modules should not depend on each other's infrastructure.
- Cross-module dependencies should go through application APIs or shared domain concepts.
- Avoid creating `shared` catch-all layers.

## Shared Core Monorepo

Typical layers:

- `core_domain`.
- `core_application`.
- `api_interface`.
- `worker_interface`.
- `shared_infrastructure`.

Direction:

- Apps/services depend on core.
- Core does not depend on apps/services.
- Shared infrastructure should not leak into core domain.

## Trading / ccxt-Style System

Typical layers:

- `strategy_domain`: signals, strategy rules, market concepts.
- `risk_domain`: limits, sizing, exposure rules.
- `execution_application`: order orchestration and idempotency.
- `exchange_adapters`: ccxt clients, exchange quirks, retry/rate-limit handling.
- `market_data_infrastructure`: feeds, storage, cache.
- `interface`: CLI, API, schedulers, bots.

Direction:

- Strategy and risk domains must not import `ccxt`, HTTP clients, persistence, or framework code.
- Execution application coordinates ports and domain decisions.
- Exchange adapters depend inward and own exchange-specific failure modes.
- CI should block new domain imports from `ccxt`, `requests`, `httpx`, SDKs, and persistence packages in medium/strict mode.
