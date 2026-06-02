---
document_type: core-entry
title: AI Agent Workspace (.agent)
status: approved
scope: project-entry
authority:
  - agent-workspace-structure
  - agent-interoperability-protocol
author: Claude Sonnet 4.5
created: 2024-01-15
last_updated: 2026-05-22
related_docs:
  - AGENTS.md
  - SOUL.md
  - STRUCTURE.md
  - docs/standards/v3/git-workflow-standard.md
  - docs/standards/v3/skill-trigger-standard.md
---

# AI Agent Workspace (.agent)

**这是 AI Agent (Claude, OpenCode, Codex, Trae, etc.) 的指定工作环境。**

所有与本项目交互的 AI 工具都必须参考此目录以了解项目上下文、工作流和规则。

## 🔗 核心链接 (Core Links)
- **[AGENTS.md](../AGENTS.md)**: Agent 全局入口
- **[CLAUDE.md](../CLAUDE.md)**: 技术栈与上下文
- **[SOUL.md](../SOUL.md)**: 核心原则与价值观 (Constitution & Principles)
- **[docs/standards/glossary.md](../docs/standards/glossary.md)**: 项目术语真源
- **[docs/standards/action-verbs.md](../docs/standards/action-verbs.md)**: 高频 动作词真源

## 📂 目录结构 (Directory Structure)

- **`../.claude/rules/`**: 具体的编码标准和项目规则真源。
  - `coding-standards.md`: 实现、边界、工具与交付细则
  - `patterns.md`: 执行模式、报告模式与渐进披露模式
- **`context/`**: 记忆与任务管理
  - `memory.md`: 长期记忆，记录关键决策和架构选择（日常记忆优先使用 `claude-memory` MCP 工具）。
  - `task.md`: **[UNTRACKED]** 由 `vibe3 handoff` 命令自动管理的短期上下文，不建议手动编辑。
  - `handoff`: 由 `vibe3 handoff status` 读取，`vibe3 handoff append` 写入的当前 flow 交接事实。
- **`workflows/`**: **workflow 层入口**。只负责编排、委托和停点，不承载复杂业务逻辑。
- **`plans/`**: 临时计划工作区。只放工作中的 plan，不作为长期真源。
- **`reports/`**: 临时报告工作区。只放工作中的 report，不作为长期真源。
- **`templates/`**: Commit, PR 等模板。
- **`../skills/`**: **skill 层真源**。负责对象判断、shell 调用顺序、blocker / handoff 逻辑。

## 🧭 Namespace 约定

- `workflow` 使用 `vibe:*`
  - 例：`vibe:new`、`vibe:continue`、`vibe:commit`
- `skill` 使用 `vibe-*`
  - 例：`vibe-new`、`vibe-continue`、`vibe-commit`

兼容期内，用户仍可使用 `/vibe-new`、`/vibe-continue` 等 slash 入口；这些入口触发的是 workflow，workflow 再委托同名 skill。

## 🤖 AI 互操作协议 (AI Interoperability Protocol)

为了确保不同 AI IDE 和 Agent 行为一致：
1.  **先读上下文**: 开始任务前，运行 `vibe3 handoff status` 和 `vibe3 flow show` 了解当前上下文，阅读 `context/memory.md`。
2.  **遵循工作流**: 如果用户请求匹配下方的工作流，请**严格按步骤执行**。
3.  **遵循约束**: 优先使用现有的能力（如 Skills），不要重新发明轮子。
4.  **更新上下文**: 任务完成后，运行 `vibe3 handoff append` 记录状态，更新 `context/memory.md`。
5.  **留存到主链**: 需要长期保留的发现或决策，写入 issue comment 或 PR comment，而不是只留在临时 plan/report。
6.  **遇到歧义先查真源**: 名词看 `glossary.md`，动词看 `action-verbs.md`，执行细则看 `../.claude/rules/`。

---

# Agent Workflows (工作流)

此目录包含 AI Agent 可直接调用的标准化 workflow 入口。workflow 只负责流程，不负责复杂业务判断。

## 🚀 开发工作流 (Development)

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/vibe-new](workflows/vibe:new.md)** | 规划入口 | intake 新目标、handoff 或缺 spec 的 task，委托 `vibe-new` skill 产出 plan 和 task 绑定。 |
| **[/vibe-continue](workflows/vibe:continue.md)** | 执行入口 | 执行当前 flow 已绑定且带 plan 的 task，委托 `vibe-continue` skill 按图纸推进。 |
| **[/vibe-commit](workflows/vibe:commit.md)** | 提交与发 PR 入口 | 读取工作区和 flow 事实，再委托 `vibe-commit` skill 处理提交分组与 PR 切片。 |

## 🧩 专项 workflow

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/vibe-task](workflows/vibe:task.md)** | task 总览与 registry 审计 | 委托 `vibe-task` skill 处理跨 worktree 总览与 roadmap-task 修复。 |
| **[/vibe-check](workflows/vibe:check.md)** | runtime 检查与修复 | 委托 `vibe-check` skill 处理 `task <-> flow` / runtime 问题。 |
| **[/vibe-issue](workflows/vibe:issue.md)** | issue intake | 委托 `vibe-issue` skill 处理 repo issue 创建、查重与补全。 |
| **[/vibe-save](workflows/vibe:save.md)** | 会话保存 | 委托 `vibe-save` skill 写回本地 handoff。 |

---

### 新增入口时的边界

直接在 `workflows/` 目录下添加 `.md` 文件前，先确认：

- 如果文档主要描述入口、阶段顺序、委托关系和停止点，它属于 workflow。
- 如果文档需要解释对象边界、shell 读取顺序、fallback / blocker / handoff，它应该放进 `skills/<name>/SKILL.md`。

workflow 模板应保持薄：

```markdown
---
name: "vibe:<name>"
description: [只写入口和委托语义]
---

1. 说明入口作用
2. 委托到对应 skill
3. 说明停点与下一步
```
