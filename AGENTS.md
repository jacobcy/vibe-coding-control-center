# AI Agent Guide

Welcome, AI Agent. This file serves as your entry point to Vibe Center 2.0.

## 📍 Project Identity
This project has **two dimensions** (see CLAUDE.md for details):
1. **Zsh CLI** — Shell scripts for AI tool/environment management (`bin/`, `lib/`)
2. **Vibe Coding Framework** — Prompt-engineered skills controlling agent behavior (`skills/`)

## 📍 Your Workspace
- **Skills** (canonical source): `skills/` at project root
- **Workflows, rules, context**: `.agent/` directory
- **Skills (runtime)**: `.agent/skills/` — symlinks, see DEVELOPER.md §Setup

## 📚 Essential Reading
1. **[CLAUDE.md](CLAUDE.md)** — Project context, tech stack, and **HARD RULES**
2. **[SOUL.md](SOUL.md)** — Core constitution and principles
3. **[.agent/README.md](.agent/README.md)** — Workflows, skills, and rules

## 🤖 Protocol
Regardless of your identity (Claude, OpenCode, Codex, Trae, etc.):
1. **Read** `.agent/context/task.md` for current task status
2. **Read** `.agent/context/memory.md` for historical decisions
3. **Follow** workflows in `.agent/workflows/`
4. **Respect** rules in `.agent/rules/` and CLAUDE.md §HARD RULES
5. **Respond** in Chinese (中文回复)

## 🚀 Quick Start
1. Read `CLAUDE.md` to understand the project
2. Read `.agent/rules/coding-standards.md` for code standards
3. Check `.agent/context/task.md` for current work
4. Run `bin/vibe check` to verify environment

## 📦 External Dependencies (Recommended)
This project uses community skills that enhance agent capabilities:
- **[Superpowers](https://github.com/jomifred/superpowers)** — General agent skills (brainstorming, TDD, debugging, etc.)
- **[OpenSpec](https://github.com/OpenSpec)** — Structured change management workflow

Install via the respective tools, then create symlinks in `.agent/skills/`.
See [DEVELOPER.md](DEVELOPER.md) for setup instructions.
