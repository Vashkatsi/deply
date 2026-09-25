---
layout: default
title: Documentation Home
nav_exclude: true
---

# Deply Documentation

Welcome to the Deply documentation! This documentation will help you understand and use Deply effectively.

## Table of Contents

1. [Getting Started]({{ site.baseurl }}/doc/getting-started.html)
   - Installation
   - Basic Usage
   - Configuration

2. [Features]({{ site.baseurl }}/doc/features.html)
   - Layer-Based Analysis
   - Dynamic Layer Configuration
   - Cross-Layer Dependency Rules
   - Extensibility

3. [Configuration Guide]({{ site.baseurl }}/doc/configuration.html)
   - Configuration File Structure
   - Layer Definitions
   - Rules and Collectors
   - [Full Stack FastAPI Template]({{ site.baseurl }}/doc/full-stack-fastapi-template.html)
   - [Architecture Styles]({{ site.baseurl }}/doc/architectures.html)
   - Examples

4. [Collectors Reference]({{ site.baseurl }}/doc/collectors.html)
   - BoolCollector
   - ClassInheritsCollector
   - ClassNameRegexCollector
   - FunctionNameRegexCollector

5. [Rules]({{ site.baseurl }}/doc/rules.html)
   - Rule Types
   - Rule Configuration
   - Common Patterns
   - Best Practices

6. [Mermaid Diagrams]({{ site.baseurl }}/doc/mermaid.html)
   - Generating Diagrams
   - Diagram Elements
   - Example Diagrams
   - Best Practices

7. [Command Line Interface]({{ site.baseurl }}/doc/cli.html)
   - Available Commands
   - Command Line Arguments
   - Output Formats
   - Examples

8. [Agent Skill]({{ site.baseurl }}/doc/skills.html)
   - Codex and Claude Code installation
   - Config generation workflow
   - CI integration

## About Deply

Deply is a standalone Python tool for enforcing architectural patterns and dependencies in large Python projects. By analyzing code structure and dependencies, this tool ensures that architectural rules are followed, promoting cleaner, more maintainable, and modular codebases.

[![PyPI version](https://img.shields.io/pypi/v/deply)](https://pypi.org/project/deply/)
[![PyPI Stats](https://pypistats.com/api/badges/deply?period=month)](https://pypistats.com/packages/deply)
[![CI](https://github.com/Vashkatsi/deply/actions/workflows/ci.yml/badge.svg)](https://github.com/Vashkatsi/deply/actions/workflows/ci.yml)
[![Python versions](https://img.shields.io/pypi/pyversions/deply)](https://pypi.org/project/deply/)
