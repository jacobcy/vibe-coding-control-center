---
document_type: standard
title: Vibe3 Handoff Governance Standard
status: approved
scope: handoff-governance
authority:
  - handoff-boundary
  - handoff-maintenance
  - handoff-read-write-rules
author: Sisyphus-Junior
created: 2026-03-24
last_updated: 2026-03-24
related_docs:
  - AGENTS.md
  - CLAUDE.md
  - docs/standards/v3/git-workflow-standard.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/handoff-store-standard.md
---

# Vibe3 Handoff Governance Standard

本文档定义 Vibe 3.0 handoff 系统的治理规则，以及 agent 和 skill 在读取、写入、修正 handoff 时的统一义务。

## 1. Scope

本文档只定义：

- handoff 的角色边界
- handoff 的读取顺序
- handoff 的写入与修正义务
- handoff 与共享真源、git 现场之间的优先级

本文档不定义：

- SQLite schema 详情（见 `handoff-store-standard.md`）
- Python CLI 实现语义
- task / flow / PR 的业务生命周期

## 2. Core Rule (Handoff Security & Access)

`.git/vibe3/handoff/` 目录及其子目录是 V3 Handoff 系统的**物理存储位置**。

**硬禁令 (Security Mandate)**：
为确保系统安全与多 worktree 环境下的权限一致性，**严禁**任何 Agent 或 Skill 直接通过文件系统 API 访问、读取或写入该目录及其内容。

1. **必须且只能通过 CLI**：所有 Handoff 操作**必须且只能**通过 `vibe3` CLI 命令完成（例如 `vibe3 handoff show`、`vibe3 handoff append`）。
2. **物理访问拒绝**：在 Worktree 隔离环境下，直接访问该物理目录会被文件系统权限拒绝（external_directory 权限限制）。
3. **调用面统一**：无论是读取 Artifact 还是追加 Context，CLI 是唯一的合法通道。

Handoff 的核心作用是传递 Agent、Skill 或 Session 之间的短期上下文：

- 本轮已完成 (Achievements)
- 阻塞原因 (Blockers)
- 临时判断与发现 (Findings)
- 下一步建议 (Next Steps)
- 关键变更文件 (Key Files)

它不得替代：

- `vibe3` Python CLI 提供的实时状态事实。
- SQLite handoff store (`.git/vibe3/handoff.db`)。
- 当前 `git` 现场事实。
- 严禁依赖 `.agent/context/task.md` 作为跨 session 或跨 skill 的真源（该文件已废弃）。

## 3. Priority Order (优先级顺序)

当 handoff 信息与其他来源冲突时，优先级固定为：

1. **共享真源** (Shared Truth): SQLite store + `vibe3` CLI 实时输出。
2. **现场事实** (Live Context): 当前 git/worktree/PR 物理现场。
3. **Handoff Buffer**: `.git/vibe3/handoff/<branch>/current.md`。

因此：

- handoff 只能补充解释，不能覆盖或伪造事实。
- handoff 不能作为当前执行阶段决策的唯一依据。
- 若 handoff 内容与现场事实冲突，必须以事实为准。

## 4. Read Rule (读取规则)

任何 agent 或 skill 读取 handoff 前，必须先通过 `vibe3` 命令核查：

1. **当前状态** (`vibe3 flow show` 或 `vibe3 task status`)。
2. **现场完整性** (`vibe3 check` 或 `git status`)。
3. **补充线索**：最后读取 handoff md 文件作为解释性补充。

禁止：

- 先读 handoff，直接把其中文案结论升格为当前事实继续执行。
- 在真源缺失时，盲目使用 handoff 作为替代真源。


## 5. Maintenance Duty

任何 agent 或 skill 只要读取了 handoff，就承担最小维护义务。

若读取后发现 handoff 与当前事实不一致，必须执行以下动作之一：

1. 修正 handoff buffer
2. 明确将其标记为过时线索，并在退出前写回更新后的 handoff

不允许：

- 明知 handoff 已过时却不修正
- 读取 handoff 后把陈旧判断继续传给下一个环节

## 6. Write Rule

以下场景退出前必须更新 handoff buffer：

- 完成一个阶段切换
- 完成一次显著的现场判断
- 处理完当前 skill 的主要交付动作
- 发现原 handoff 已经过时

推荐 handoff buffer 至少覆盖：

- 当前任务
- 当前现场
- 本轮已完成
- 当前判断
- blockers
- 下一步
- 关键文件

若当前 flow 对应 PR 已 merged，则 handoff 只允许补记：

- 交付证据
- 审计说明
- handoff 更正
- follow-up 链接

禁止把 merge 后出现的新需求、新目标或新开发范围继续写回旧 plan；这些内容必须进入新的 `GitHub issue`，并按需要重新进入 `roadmap item` 与后续 execution record。

## 7. Root-Doc Requirement

`CLAUDE.md` 必须把 handoff 边界作为入口级规则明确告知所有 agent。

skill 可以引用本文档，但不应各自重写一套 handoff 宪法。

## 8. Restrictions

- 不得把 handoff buffer 写成共享状态缓存层
- 不得把 handoff 当作"通常是新鲜的事实副本"
- 不得让 skill 通过自由文案发明新的 handoff 规则
- 不得把"用户没要求更新 handoff"当作放弃修正过时 handoff 的理由

## 9. Legacy (Migration from V2)

以下内容仅供从 V2 迁移时参考，V3 原生开发可忽略。

V2 到 V3 handoff 系统的关键变化：

| 方面 | V2 (Shell) | V3 (Python) |
|------|------------|-------------|
| 存储 | `.agent/context/task.md` (已废弃) | SQLite + Markdown buffer |
| 路径 | `.git/vibe/` | `.git/vibe3/` |
| 命令 | `vibe2 flow` (Legacy/Deprecated) | `vibe3` Python CLI |
| 主键 | worktree name | branch name |
| 关系 | issue links 内嵌 | 独立表 `flow_issue_links` |

迁移检查清单：

- [ ] 更新所有 `vibe` shell 命令引用为 `vibe3` Python CLI
- [ ] 更新路径引用 `.git/vibe/` → `.git/vibe3/`
- [ ] 更新 handoff buffer 访问方式：严禁直接读写文件，改用 `vibe3 handoff show/append`
- [ ] 更新 handoff buffer 概念：存储于 `.git/vibe3/handoff/<branch>/` (系统内部路径)，由 CLI 抽象访问
- [ ] 移除对 `task.md` 的依赖，改用 SQLite 作为真源
- [ ] 更新相关文档引用到 v3 版本

(End of file)
