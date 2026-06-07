---
document_type: core-entry
title: AI Agent Guide
status: approved
scope: project-entry
authority:
  - agent-entry-navigation
  - essential-reading-order
author: Claude Sonnet 4.5
created: 2024-01-15
last_updated: 2026-06-02
related_docs:
  - SOUL.md
  - STRUCTURE.md
  - CLAUDE.md
---

# AI Agent Guide

Welcome, AI Agent. This file serves as your entry point to Vibe Center 3.0.

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
4. **[docs/standards/agent-document-lifecycle-standard.md](docs/standards/agent-document-lifecycle-standard.md)** — Temporary docs and comment retention rules
5. **[docs/standards/glossary.md](docs/standards/glossary.md)** — Project terminology
6. **[docs/decisions/INDEX.md](docs/decisions/INDEX.md)** — Architecture Decision Records
7. **[docs/standards/action-verbs.md](docs/standards/action-verbs.md)** — Action verb definitions
8. **[.agent/README.md](.agent/README.md)** — AI workflows and rules
9. **[docs/README.md](docs/README.md)** — Documentation structure

## 🔄 Key Workflows (工作流)

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/vibe-new](.agent/workflows/vibe:new.md)** | 规划入口 | intake 新目标、handoff 或缺 spec 的 task，产出 plan 和 task 绑定。 |
| **[/vibe-continue](.agent/workflows/vibe:continue.md)** | 执行入口 | 执行当前 flow 已绑定且带 plan 的 task，按图纸推进实现。 |
| **[/vibe-commit](.agent/workflows/vibe:commit.md)** | 提交入口 | 读取工作区事实，处理提交分组与 PR 切片。 |
| **[/vibe-task](.agent/workflows/vibe:task.md)** | 任务总览 | 处理跨 worktree 总览与 roadmap-task 状态修复。 |
| **[/vibe-check](.agent/workflows/vibe:check.md)** | 运行时检查 | 处理 `task <-> flow` / runtime 状态不一致。 |
| **[/vibe-issue](.agent/workflows/vibe:issue.md)** | Issue 管理 | 处理 GitHub issue 创建、查重与补全。 |
| **[/vibe-save](.agent/workflows/vibe:save.md)** | 会话保存 | 将当前会话上下文持久化到本地 handoff。 |

## 🛡️ V2 Legacy Aliases (Compatibility)

For backward compatibility with V2 workflows, the following aliases are supported but **demoted** in favor of V3 native commands:

| Alias | Demoted To (V3) | Status |
| :--- | :--- | :--- |
| `wtnew` | `vibe3 flow update` | Supplementary |
| `vup` | `vibe3 flow update` | Supplementary |

> **Recommendation**: Prefer `vibe3` native commands for all new development flows.

## 📍 Project Identity

V3 是默认执行链：flow、handoff、orchestra 和 role dispatch 的语义真源都在 V3 Python + `docs/standards/v3/`。V2 仍然存在，但只作为兼容入口和环境工具。

This project has **two parallel implementations**:

1. **V2 (Shell)** — Zsh alias 和环境工具（`bin/`, `lib/`, `config/shell/aliases.sh`）
2. **V3 (Python)** — issue/flow/PR 管理主系统（`src/vibe3/`, `tests/vibe3/`）

> branch 生命周期优先直接使用 `git`，issue / PR 远端操作优先直接使用 `gh`，`vibe3` 负责本地 flow scene、events 与 handoff 增强。

## 📍 Workspace Structure

- **V2 (Shell)**: `bin/`, `lib/`, `config/shell/`
- **V3 (Python)**: `src/vibe3/` (Support global `vibe3` command via `uv tool install -e .`)
- **V3 Hub**: `lib3/` (V3 Python 核心包装器与仓库重定向)
- **Skills**: `skills/`（各技能的 SKILL.md 文件）
- **Workflows, rules, context**: `.agent/`
- **Shared state truth**: `.git/vibe3/handoff.db`（位于主仓库 git common dir，即最顶层 `.git`）

## 🚀 Quick Start

1. **查看项目导览**: 阅读 `skills/vibe-instruction/SKILL.md`
2. **检查当前 flow**: 运行 `vibe3 flow show`
3. **查看全局状态**: 运行 `vibe3 status`
4. **了解执行规则**: 阅读 [.claude/rules/coding-standards.md](.claude/rules/coding-standards.md)

## 🔁 Handoff 命令约定

- `vibe3 handoff status [branch]`：查看当前 flow 或指定 branch 的 handoff 现场
- `vibe3 handoff show <artifact-path>`：读取共享 handoff artifact
- `vibe3 handoff verdict`：提交任务执行裁决（PASS/MAJOR/BLOCK/UNKNOWN）
- `vibe3 handoff plan/report/audit/next`：记录特定阶段的责任链上下文
- `handoff show` 不再用于状态总览；遇到 `vibe3/handoff/...` 这类共享路径时，应通过 `handoff show <path>` 读取

## 架构层级 (Three-Tier Architecture)

> **语义真源**：详细定义详见 [docs/standards/glossary.md](docs/standards/glossary.md)

- **Tier 3 (Cognitive/Governance)**: Policies, rules, supervisor. (Rules and Principles)
- **Tier 2 (Skill Layer)**: Orchestration and context management. (Workflow and Logic)
- **Tier 1 (Shell Layer)**: Atomic capabilities and state access. (Tools and Execution)

## 🤖 Protocol

Regardless of your identity (Claude, OpenCode, Codex, Trae, etc.):
- **Respond** in Chinese (中文回复)
- **Respect** hard rules in [CLAUDE.md](CLAUDE.md)
- **Follow** workflows in `.agent/workflows/`

## ⚠️ Important Principles (Hard Rules)

这些原则选自 [CLAUDE.md](CLAUDE.md)，Agent 必须严格遵守：

1. **本地测试节奏 (CI 优先)**：
   - **避免全量测试**：本地默认执行**定向回归测试**。
   - **禁止在同一轮修改中反复运行全量 `uv run pytest`**。
   - 全量测试交给线上 CI；创建 PR draft 后查看 CI 结果。
   - 仅在用户明确要求或复现 CI 特有失败时才本地跑全量。

2. **Git 纪律 (强制两步提交)**：
   - ✅ **第一步**：temp commit -> pre-commit 自动修复格式问题。
   - ✅ **第二步**：reset -> 正式分组提交（按功能模块）。
   - ❌ 禁止使用 `--no-verify` 绕过质量门禁。

3. **署名规则**：
   - ✅ Issue/PR 创建必须包含贡献者列表或署名。
   - ✅ Comment 必须明确标注发布者身份。

4. **最短路径优先**：
   - 优先复用现有命令/流程，避免新增边缘命令或过度工程化。

5. **技术栈约束**：
   - **必须使用 `uv run`**，禁止直接使用 `python`/`pip`。
   - 禁止在文档/输出中使用线框图 (box drawing characters)，使用 YAML/Mermaid/ASCII。

## 📦 External Dependencies

This project uses community skills:
- **[Superpowers](https://github.com/jomifred/superpowers)** — General agent skills
- **[OpenSpec](https://github.com/OpenSpec)** — Structured change management

Install via respective tools, then create symlinks in `.claude/skills/`. See [DEVELOPER.md](DEVELOPER.md) for setup.

## 代码分析工具

- `vibe3 inspect symbols/files/base/pr/commit` — 代码结构与影响分析

- `claude-memory smart search` — 项目记忆搜索（跨对话上下文）
- 详细用法见 [supervisor/policies/common.md](supervisor/policies/common.md)

## 🔗 Kiro Integration

When using Kiro (AI IDE with spec workflow), follow rules in [supervisor/policies/kiro-integration.md](supervisor/policies/kiro-integration.md).
