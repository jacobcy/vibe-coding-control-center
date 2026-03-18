# AI Agent Guide

Welcome, AI Agent. This file serves as your entry point to Vibe Center 2.0.

> **Single Entry Policy**: `AGENTS.md` is the canonical root entry for all agents.
> **Single Source of Truth**: Each document has a specific responsibility. See [SOUL.md](SOUL.md) §0 for document responsibility matrix.
> If other root-level agent files exist, treat them as aliases and follow this file.

## 📚 Essential Reading

Follow this reading order. Each document is the authority for its domain:

1. **[SOUL.md](SOUL.md)** — Core constitution and principles
2. **[STRUCTURE.md](STRUCTURE.md)** — Project structure definition
3. **[CLAUDE.md](CLAUDE.md)** — Project context, tech stack, and hard rules
4. **[docs/standards/glossary.md](docs/standards/glossary.md)** — Project terminology
5. **[docs/standards/action-verbs.md](docs/standards/action-verbs.md)** — Action verb definitions
6. **[.agent/README.md](.agent/README.md)** — AI workflows and rules
7. **[docs/README.md](docs/README.md)** — Documentation structure

## 📍 Project Identity

This project has **two parallel implementations**:
1. **V2 (Shell)** — Zsh implementation (`bin/`, `lib/`, `tests/vibe2/`)
2. **V3 (Python)** — Python implementation (`src/vibe3/`, `tests/vibe3/`)

## 📍 Workspace Structure

- **V2 (Shell)**: `bin/`, `lib/`, `config/`
- **V3 (Python)**: `src/vibe3/` (see [.agent/rules/python-standards.md](.agent/rules/python-standards.md))
- **Skills**: `skills/`
- **Workflows, rules, context**: `.agent/`
- **Shared state truth**: `.git/vibe/`

## 🚀 Quick Start

1. **Verify environment**: Run `bin/vibe check`
2. **Check current work**: Read `.agent/context/task.md`
3. **Understand execution rules**: Read [.agent/rules/coding-standards.md](.agent/rules/coding-standards.md) and [.agent/rules/patterns.md](.agent/rules/patterns.md)

## 🤖 Protocol

Regardless of your identity (Claude, OpenCode, Codex, Trae, etc.):
- **Respond** in Chinese (中文回复)
- **Respect** hard rules in [CLAUDE.md](CLAUDE.md)
- **Follow** workflows in `.agent/workflows/`

## 📦 External Dependencies

This project uses community skills:
- **[Superpowers](https://github.com/jomifred/superpowers)** — General agent skills
- **[OpenSpec](https://github.com/OpenSpec)** — Structured change management

Install via respective tools, then create symlinks in `.agent/skills/`. See [DEVELOPER.md](DEVELOPER.md) for setup.

## 🔗 Kiro Integration

When using Kiro (AI IDE with spec workflow), follow rules in [.agent/rules/kiro-integration.md](.agent/rules/kiro-integration.md).