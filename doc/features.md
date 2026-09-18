---
layout: default
title: Features
nav_order: 3
---

# Deply Features

Deply provides several powerful features to help you maintain clean architecture in your Python projects.

## Layer-Based Analysis

Deply allows you to define project layers and restrict their dependencies to enforce modularity. This helps maintain a clean separation of concerns in your codebase.

## Dynamic Layer Configuration

You can easily configure collectors for each layer using:
- File patterns
- Class inheritance
- Logical conditions
- Custom collectors

This flexibility allows you to adapt Deply to your project's specific needs.

## Cross-Layer Dependency Rules

Specify rules to control how different layers can interact with each other. For example:
- Prevent views from directly accessing models
- Enforce service layer patterns
- Control access to specific functionality

Internal imports inside functions, async functions, methods, and class bodies
are attributed only to the nearest enclosing definition when it is collected.
Imports inside an uncollected definition are not attributed to other elements.
Module-level imports still apply to every collected element in the file.
Internal target matching remains heuristic: module identities, import aliases,
relative imports, and shadowing are not reliably resolved. This ownership policy
does not change the separate external-import rules.

## Extensible and Configurable

Deply is configurable and extensible through:
- Custom collectors for specific needs
- Supported naming, decorator, inheritance, dependency, and external-import rules
- Support for various project structures
- Integration with existing codebases

## Key Benefits

1. **Clean Architecture**: Enforce architectural boundaries and prevent unwanted dependencies
2. **Maintainability**: Keep your codebase organized and easier to maintain
3. **Scalability**: Scale your project while maintaining architectural integrity
4. **Documentation**: Automatically document your project's architecture
5. **Quality Control**: Catch architectural violations early in the development process

For detailed information about implementing these features, please refer to the [Configuration Guide](configuration.html) and [Collectors Reference](collectors.html).
