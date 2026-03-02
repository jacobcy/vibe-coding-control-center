---
task_id: "2026-03-02-task-readme-audit"
document_type: task-plan
title: "Task README Status Field Audit & Cleanup"
author: "Antigravity Agent"
created: "2026-03-02"
last_updated: "2026-03-02"
status: planning
---

# Task README Status Field Audit & Cleanup

## 1. 背景

在检查 `docs/tasks/2026-03-02-vibe-task/README.md` 时，发现 frontmatter 中的 `status` 字段
与正文中的 `**状态**:` 字段存在**语义冲突**（一个是 `completed`，另一个是 `In Progress`）。

这是一个跨任务的系统性问题：正文里的状态跟不上 frontmatter 的更新，导致任务文档存在双头
真源、混淆状态的情况。

**根本原则：frontmatter `status:` 是唯一真源，正文里的状态字段应删除或替换为
"见 frontmatter status 字段"的指引。**

另一个在本次评审中暴露出的相关问题是**收口边界**：
一旦 PR 已合并并进入 `/vibe-done` 阶段，系统不应再修改 worktree 内受 Git 追踪的文件。
这意味着 `docs/tasks/.../README.md` 的状态字段和 `tasks/<task-id>/task.json.status` 都不应再承担
Post-PR 收口真源的职责；收口后的运行期状态应只存在于 `.git/vibe/` 下的共享 registry 元数据。

## 2. 审计结果

以下是 `2026-03-02` 审计时发现的**存在状态冲突**的文件：

| 文件 | frontmatter status | 正文状态 | 冲突？ |
|---|---|---|---|
| `2026-03-02-cross-worktree-task-registry/README.md` | `completed` | `In Progress` | ⚠️ **冲突** |
| `2026-03-01-session-lifecycle/README.md` | `completed` | `In Progress` | ⚠️ **冲突** |
| `2026-03-02-rotate-alignment/README.md` | `todo` | `Todo` | ✅ 一致（但仍冗余） |
| `2026-03-02-command-slash-alignment/README.md` | `todo` | `Todo` | ✅ 一致（但仍冗余） |

以下文件**不存在冲突**（正文状态与 frontmatter 一致，但仍需清理冗余）：

| 文件 | 备注 |
|---|---|
| `2026-02-26-agent-dev-refactor/README.md` | archived / Archived 一致 |
| `2026-02-25-vibe-v2-final/README.md` | archived / Archived 一致 |
| `2026-02-21-save-command/README.md` | archived / Archived 一致 |
| `2026-02-26-vibe-engine/README.md` | archived / Archived 一致 |
| `2026-02-21-vibe-architecture/README.md` | archived / Archived 一致 |
| `2026-02-28-vibe-skills/README.md` | 无正文状态字段，干净 |

以下文件**已修复**（本次 PR 期间处理）：

| 文件 | 处理方式 |
|---|---|
| `2026-03-02-vibe-task/README.md` | 正文改为指引至 frontmatter |

## 3. 执行计划

### Phase A：修复冲突文件（优先级：高）
- `2026-03-02-cross-worktree-task-registry/README.md`：将正文 `In Progress` 改为指引至 frontmatter。
- `2026-03-01-session-lifecycle/README.md`：同上。

### Phase B：清理冗余字段（优先级：中）
统一将所有正文中 `- **状态**: xxx` 的行替换为
`- **状态**: 见 frontmatter \`status\` 字段（唯一真源）`，
或直接删除该行（正文不需要重复显示状态）。
涉及：rotate-alignment、command-slash-alignment、以及所有 archived 任务。

### Phase C：建立文档规范（优先级：中）
在 `docs/standards/` 中建立或更新 Task README 格式规范文档，明确：
- frontmatter `status` 是唯一真源；
- 正文禁止出现独立的状态字段；
- gates 状态（test/code/audit）必须在 PR 合并前通过 commit 更新完毕。

### Phase D：收口边界与 `task.json.status` 退役（优先级：高，下次任务处理）
本阶段只记录问题，不在当前 worktree 内继续实现。

目标：
- 明确 `/vibe-done` 之后只允许写 `.git/vibe/registry.json` 与 `.git/vibe/worktrees.json`。
- 明确 `tasks/<task-id>/task.json` 不能再作为收口阶段的状态真源。
- 将 `task.json.status` 从现有 skill / 文档契约中降级为非真源字段，或直接删除该字段。

需要下次一并审计的范围：
- `skills/vibe-done/SKILL.md`
- `skills/vibe-save/SKILL.md`
- `skills/vibe-continue/SKILL.md`
- `skills/vibe-task/SKILL.md`
- 任何把 `task.json.status` 描述为真实状态来源的计划或标准文档

验收标准：
- `/vibe-done` 的收口说明只包含 `.git/vibe/` 下的 JSON 写操作。
- `task.json` 仅保留 task 结构、subtask 结构、计划路径等静态或开发期信息，不再作为 completed/archived 状态真源。
- `/continue`、`/save`、`/task` 对运行期状态的读取统一以共享 registry 为准，不再依赖 `task.json.status`。

---
**本期不执行。下一个工作树中作为独立任务处理。**
