# AI Agent Guide

Welcome, AI Agent. This file serves as your entry point to Vibe Center 2.0.

> **Single Entry Policy**: `AGENTS.md` is the canonical root entry for all agents.
> **Single Source of Truth**: Each document has a specific responsibility. See [SOUL.md](SOUL.md) §0 for document responsibility matrix.
> If other root-level agent files exist, treat them as aliases and follow this file.

## 🗺️ 项目导览（先读这个）

**不熟悉本项目？先运行 `/vibe-instruction`**（技能文件：`skills/vibe-instruction/SKILL.md`）

该技能解释：
- vibe2 shell 和 vibe3 python 各自负责什么
- vibe3 的核心命令（`flow update/show/status/bind/blocked`、`status`、`handoff` 等）
- 标准开发工作流（`/vibe-new` → 编码 → `/vibe-commit` → `/vibe-integrate` → `/vibe-done`）
- 常见场景速查

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

1. **V2 (Shell)** — Zsh alias 和环境工具（`bin/`, `lib/`, `config/aliases.zsh`）
2. **V3 (Python)** — issue/flow/PR 管理主系统（`src/vibe3/`, `tests/vibe3/`）

> V2 主要提供 alias（`wtnew`、`vup`）和环境工具；branch 生命周期优先直接使用 `git`，issue / PR 远端操作优先直接使用 `gh`，`vibe3` 负责本地 flow scene、events 与 handoff 增强。

## 📍 Workspace Structure

- **V2 (Shell)**: `bin/`, `lib/`, `config/`
- **V3 (Python)**: `src/vibe3/` (see [.agent/rules/python-standards.md](.agent/rules/python-standards.md))
- **Skills**: `skills/`（各技能的 SKILL.md 文件）
- **Workflows, rules, context**: `.agent/`
- **Shared state truth**: `.git/vibe3/`（位于主仓库 git common dir，即最顶层 `.git`）

## 🚀 Quick Start

1. **查看项目导览**: 阅读 `skills/vibe-instruction/SKILL.md`
2. **检查当前 flow**: 运行 `uv run python src/vibe3/cli.py flow show`
3. **查看全局状态**: 运行 `uv run python src/vibe3/cli.py status`
4. **了解执行规则**: 阅读 [.agent/rules/coding-standards.md](.agent/rules/coding-standards.md)

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