---
layout: default
title: Architecture Styles
parent: Configuration
nav_order: 4
has_children: true
---

# Architecture and Pattern Recipes

These recipes show how to express common source-code boundaries with Deply.
They are editable starting points, not built-in presets. Architecture styles
can be combined: a modular monolith can use hexagonal boundaries inside each
module, while one complex module can use CQRS or event sourcing.

Deply checks static structure and imports. It cannot prove runtime properties
such as transactionality, message delivery, idempotency, consistency, retries,
deployment isolation, or operational ownership.

## Choose by Design Problem

| Design problem | Start with |
| --- | --- |
| Organize dependencies into conventional tiers | [Layered / N-tier](architectures/layered.html) |
| Isolate the application from frameworks and external systems | [Hexagonal](architectures/hexagonal.html), [Clean](architectures/clean.html), or [Onion](architectures/onion.html) |
| Keep one deployable split into business modules | [Modular Monolith](architectures/modular-monolith.html) or [DDD / Bounded Contexts](architectures/ddd-bounded-contexts.html) |
| Organize code around features or requests | [Package by Feature](architectures/package-by-feature.html), [Vertical Slice](architectures/vertical-slice.html), or [Use-case Action](architectures/action.html) |
| Separate independent services in one repository | [Microservices Monorepo](architectures/microservices-monorepo.html) |
| Build an extensible core or processing chain | [Microkernel](architectures/microkernel.html) or [Pipe-and-Filter](architectures/pipe-and-filter.html) |
| Choose a business-logic organization style | [Transaction Script](architectures/transaction-script.html), [Service Layer](architectures/service-layer.html), or [Domain Model](architectures/ddd-bounded-contexts.html) |
| Separate reads, writes, events, and projections | [CQRS](architectures/cqrs.html), [Event-Driven](architectures/event-driven.html), or [Event Sourcing](architectures/event-sourcing.html) |
| Choose a persistence boundary | [Active Record](architectures/active-record.html), [Data Mapper](architectures/data-mapper.html), or [Repository + Unit of Work](architectures/repository-unit-of-work.html) |
| Structure server-side presentation | [MVC / MVT](architectures/mvc-mvt.html) |

## Core Architecture Styles

- [Layered / N-tier](architectures/layered.html)
- [Hexagonal / Ports and Adapters](architectures/hexagonal.html)
- [Clean Architecture](architectures/clean.html)
- [Onion Architecture](architectures/onion.html)
- [Microkernel / Plugin](architectures/microkernel.html)
- [Pipe-and-Filter](architectures/pipe-and-filter.html)

## Decomposition Styles

- [Modular Monolith](architectures/modular-monolith.html)
- [DDD / Bounded Contexts](architectures/ddd-bounded-contexts.html)
- [Package by Feature / Screaming Architecture](architectures/package-by-feature.html)
- [Vertical Slice](architectures/vertical-slice.html)
- [Microservices Monorepo](architectures/microservices-monorepo.html)

## Application Logic Styles

- [Transaction Script](architectures/transaction-script.html)
- [Service Layer](architectures/service-layer.html)
- [Use-case Action](architectures/action.html)

## Data and Messaging Styles

- [CQRS](architectures/cqrs.html)
- [Event-Driven](architectures/event-driven.html)
- [Event Sourcing](architectures/event-sourcing.html)
- [Active Record](architectures/active-record.html)
- [Data Mapper](architectures/data-mapper.html)
- [Repository + Unit of Work](architectures/repository-unit-of-work.html)

## Presentation Styles

- [MVC / MVT](architectures/mvc-mvt.html)

## Common Workflow

For every recipe:

1. Adapt directories and package names to the project.
2. Validate the configuration.
3. Run analysis and review violations before changing rules or code.

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```
