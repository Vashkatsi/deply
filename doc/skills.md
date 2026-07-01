---
layout: default
title: Agent Skill
nav_order: 9
---

# Deply Config Agent Skill

Deply v1.0.0 ships a portable Agent Skill at `skills/deply-config/`. Use it with Codex, Claude Code, or any Agent Skills-compatible assistant to create and validate `deply.yaml` for a Python project.

The skill guides the assistant through:

- repository discovery before asking questions
- deterministic discovery checklist for Python roots, frameworks, CI, docs, suppressions, and monorepos
- create/update mode for new or improved configs
- audit mode for existing `deply.yaml`, CI, docs, and suppressions
- violation triage after `deply analyze`
- architecture recipes for layered, hexagonal, Django, FastAPI, modular monolith, monorepo, and trading/ccxt-style systems
- `light`, `medium`, and `strict` architecture presets
- monorepo guidance for `apps/*`, `services/*`, `packages/*`, and `src/*`
- framework-aware collectors for Django, FastAPI, Flask, Celery, and SQLAlchemy
- install snippets for `pip`, `pipx`, `uv`, and `poetry`
- `deply validate --config=deply.yaml`
- `deply analyze --parallel --config=deply.yaml`
- Makefile, CI, and documentation updates

## Installation

For Codex, copy the skill folder into your Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R skills/deply-config "${CODEX_HOME:-$HOME/.codex}/skills/deply-config"
```

For Claude Code, copy it into your user or project skills directory:

```bash
mkdir -p "$HOME/.claude/skills"
cp -R skills/deply-config "$HOME/.claude/skills/deply-config"
```

For project-local Claude Code usage:

```bash
mkdir -p .claude/skills
cp -R skills/deply-config .claude/skills/deply-config
```

For other agents, point the agent at the `skills/deply-config/` folder as an Agent Skills-compatible skill.

## Usage

Ask your assistant:

```text
Use $deply-config to create and validate a Deply architecture config for this Python project.
```

The assistant should inspect the repository first, ask only for architecture intent, choose a matching architecture recipe, generate or audit `deply.yaml`, validate it, run analysis, triage violations, scan existing `deply:ignore` suppressions, and then add local/CI/docs integration when requested.

## Recommended CI Command

```bash
deply validate --config=deply.yaml
deply analyze --parallel --config=deply.yaml
```

For GitHub Actions, prefer:

```bash
deply analyze --parallel --report-format=github-actions --config=deply.yaml
```

If adopting Deply in a legacy project with existing violations, use an explicit temporary ratchet only after recording the current violation count:

```bash
deply analyze --parallel --config=deply.yaml --max-violations=12
```
