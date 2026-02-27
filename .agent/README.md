# AI Agent Workspace (.agent)

**这是 AI Agent (Claude, OpenCode, Codex, Trae, etc.) 的指定工作环境。**

所有与本项目交互的 AI 工具都必须参考此目录以了解项目上下文、工作流和规则。

## 🔗 核心链接 (Core Links)
- **[AGENTS.md](../AGENTS.md)**: Agent 全局入口
- **[CLAUDE.md](../CLAUDE.md)**: 技术栈与上下文
- **[SOUL.md](../SOUL.md)**: 核心原则与价值观 (Constitution & Principles)

## 📂 目录结构 (Directory Structure)

- **`context/`**: 记忆与任务管理
  - `memory.md`: 长期记忆，记录关键决策和架构选择。
  - `task.md`: 当前活动任务列表。
- **`workflows/`**: **用户接口 (User Interface)**。定义了 Agent 可执行的标准任务流程。
- **`lib/`**: **技能引擎 (Skill Engine)**。包含被 Workflow 调用的核心脚本库 (`.sh`)，实现了具体的业务逻辑。
  - `gh-ops.sh`: GitHub issue 和 PR 管理。
  - `audit.sh`: 代码与文档审计。
  - `git-scope.sh`: 变更范围分析。
  - `bump_version.sh`: 版本发布辅助脚本。
- **`rules/`**: 具体的编码标准和项目规则。
- **`templates/`**: Commit, PR 等模板。

## 🤖 AI 互操作协议 (AI Interoperability Protocol)

为了确保不同 AI IDE 和 Agent 行为一致：
1.  **先读上下文**: 开始任务前，必须阅读 `context/task.md` 和 `context/memory.md`。
2.  **遵循工作流**: 如果用户请求匹配下方的工作流，请**严格按步骤执行**。
3.  **调用技能库**: 优先使用 `lib/` 下的脚本来完成复杂操作，而不是重新发明轮子。
4.  **更新上下文**: 任务完成后，更新 `context/task.md` 和 `context/memory.md`。

---

# Agent Workflows (工作流)

此目录包含 AI Agent 可直接调用的标准化任务流程。

## 🚀 开发工作流 (Development)

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/vibe-commit](workflows/vibe-commit.md)** | 智能提交 (Smart Commit) | 由 AI 分析 `git diff`，按功能分组并交互式生成 Conventional Commits。 |

> 💡 `vibe flow sync` — 通过 CLI 将当前分支同步到所有 Worktree 分支。
> 💡 `vibe clean` — 通过 CLI 一键清理 `temp/` 及临时文件。

## 🔍 代码审查与维护 (Review & Maintenance)

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/review-code](workflows/review-code.md)** | 代码审计 (Code Audit) | 运行 ShellCheck 和逻辑检查，确保代码质量。 |
| **[/review-docs](workflows/review-docs.md)** | 文档审查 (Review Docs) | 检查 `docs/` 和 `CHANGELOG.md` 的完整性。 |

## 🐙 GitHub Issue 管理 (Issue Ops)

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/issue-create](workflows/issue-create.md)** | 创建 Issue | 交互式创建新的 GitHub Issue。 |
| **[/issue-resolve](workflows/issue-resolve.md)** | 解决 Issue | 处理并关闭指定的 GitHub Issue。 |

## 🛠️ 元工作流 (Meta)

| Workflow | Description | Usage |
| :--- | :--- | :--- |
| **[/create-workflow](workflows/create-workflow.md)** | 创建新工作流 | 引导用户创建新的 `.md` 工作流文件。 |
| **[/release](workflows/release.md)** | 自动化发布 | 构建、打标签并发布新版本。 |

---

### 如何创建新工作流
运行 `/create-workflow` 或直接在 `workflows/` 目录下添加 `.md` 文件：
```markdown
---
description: [简短描述]
---

1. 第一步
// turbo
User command...
```
