# AI Agent Guide

Welcome, AI Agent. This file serves as your entry point to Vibe Center 2.0.

> **Single Entry Policy**: `AGENTS.md` is the canonical root entry for all agents.
> **Single Source of Truth**: Each document has a specific responsibility. See [SOUL.md](SOUL.md) §0 for document responsibility matrix.
> If other root-level agent files exist, treat them as aliases and follow this file.

## 📍 Project Identity
This project has **two dimensions** (see CLAUDE.md for details):
1. **Zsh CLI** — Shell scripts for AI tool/environment management (`bin/`, `lib/`)
2. **Vibe Coding Framework** — Prompt-engineered skills controlling agent behavior (`skills/`)

## 📍 Your Workspace
- **Skills** (canonical source): `skills/` at project root
- **Workflows, rules, context**: `.agent/` directory
- **Skills (runtime)**: `.agent/skills/` — symlinks, see DEVELOPER.md §Setup

## 📚 Essential Reading

> **Reading Order**: Follow this sequence for optimal understanding. Each document is the authority for its domain (see [SOUL.md](SOUL.md) §0).

1. **[SOUL.md](SOUL.md)** — Core constitution and principles (authority on values and boundaries)
2. **[STRUCTURE.md](STRUCTURE.md)** — Project structure definition (authority on file organization)
3. **[CLAUDE.md](CLAUDE.md)** — Project context, tech stack, and **HARD RULES** (authority on technical rules)
4. **[docs/README.md](docs/README.md)** — Documentation structure and standards (authority on documentation)
5. **[.agent/README.md](.agent/README.md)** — Workflows, skills, and rules (authority on AI workflows)

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

## 🔗 Kiro Integration Rules

When using Kiro (AI IDE with spec workflow) for task management in this project:

1. **Spec Location**: Kiro specs MUST be created in `.kiro/specs/{feature-name}/` directory
   - Bugfix specs: `bugfix.md`, `design.md`, `tasks.md`
   - Feature specs: `requirements.md`, `design.md`, `tasks.md`

2. **Vibe Task Integration**: Each Kiro spec MUST have a corresponding Vibe task directory
   - Create task directory: `docs/tasks/{YYYY-MM-DD-feature-name}/`
   - Create task README: `docs/tasks/{YYYY-MM-DD-feature-name}/README.md`
   - Link Kiro spec in README's "文档导航" section

3. **Task Lifecycle**: Use `vibe task` commands to manage task lifecycle
   - Register task: `vibe task add {task-id} --title "{title}" --status todo`
   - Update status: `vibe task update {task-id} --status {status}`
   - Bind to worktree: `vibe task update {task-id} --bind-current`
   - List tasks: `vibe task list`

4. **Status Synchronization**: Keep Kiro spec and Vibe task status in sync
   - Kiro spec execution → Update `vibe task` status
   - Task completion → Update both `.kiro/specs/` and `docs/tasks/` README
   - Use frontmatter `status` field as single source of truth in task README

5. **Documentation Standards**: Follow Vibe documentation standards
   - Task naming: `YYYY-MM-DD-feature-name` (kebab-case)
   - Document naming: `{layer}-v{version}-{description}.md` or `{layer}-{description}.md`
   - Reference: [docs/standards/doc-organization.md](docs/standards/doc-organization.md)
