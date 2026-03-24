---
document_type: standard
title: Vibe3 Handoff Governance Standard
status: proposed
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

## 2. Core Rule

`.git/vibe3/handoff/<branch>/current.md` 是本地 handoff buffer，不是真源。

它只用于在 agent、skill 或会话之间传递短期上下文，例如：

- 本轮已完成
- blockers
- 临时判断
- 下一步建议
- 关键文件

它不得替代：

- `vibe3` Python CLI 提供的共享状态事实
- SQLite handoff store (`.git/vibe3/handoff.db`)
- 当前 `git` 现场事实
- 其他标准文档中的正式语义

## 3. Priority Order

当 handoff 与其他来源同时存在时，优先级固定为：

1. 共享真源（SQLite store + CLI 输出）
2. 当前 git/worktree/PR 现场事实
3. `.git/vibe3/handoff/<branch>/current.md` buffer
4. `.agent/context/task.md` 本地草稿（可选，已废弃）

因此：

- handoff 只能补充解释，不能覆盖事实
- handoff 不能作为当前阶段判断的唯一依据
- 若 handoff 与事实冲突，必须以事实为准

## 4. Read Rule

任何 agent 或 skill 如果读取 `.git/vibe3/handoff/<branch>/current.md`，必须先核查：

- 当前共享状态真源（`vibe3 flow show` 或 SQLite 直接查询）
- 当前 git 现场
- 必要时的 PR / review 事实

读取顺序必须是：

1. 先确认事实（SQLite + CLI）
2. 再读取 handoff buffer
3. 最后把 handoff 作为补充线索解释当前状态

禁止：

- 先读 handoff，再把其中结论当当前事实继续执行
- 在共享真源缺失时，直接把 handoff 升格为替代真源

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

禁止把 merge 后出现的新需求、新目标或新开发范围继续写回旧 plan；这些内容必须进入新的 `repo issue`，并按需要重新进入 `roadmap item` 与后续 execution record。

## 7. Root-Doc Requirement

`CLAUDE.md` 必须把 handoff 边界作为入口级规则明确告知所有 agent。

skill 可以引用本文档，但不应各自重写一套 handoff 宪法。

## 8. Restrictions

- 不得把 handoff buffer 写成共享状态缓存层
- 不得把 handoff 当作"通常是新鲜的事实副本"
- 不得让 skill 通过自由文案发明新的 handoff 规则
- 不得把"用户没要求更新 handoff"当作放弃修正过时 handoff 的理由

## 9. Migration from V2

V2 到 V3 handoff 系统的关键变化：

| 方面 | V2 (Shell) | V3 (Python) |
|------|------------|-------------|
| 存储 | `.agent/context/task.md` | SQLite + Markdown buffer |
| 路径 | `.git/vibe/` | `.git/vibe3/` |
| 命令 | `vibe flow` | `vibe3` Python CLI |
| 主键 | worktree name | branch name |
| 关系 | issue links 内嵌 | 独立表 `flow_issue_links` |

迁移检查清单：

- [ ] 更新所有 `vibe` shell 命令引用为 `vibe3` Python CLI
- [ ] 更新路径引用 `.git/vibe/` → `.git/vibe3/`
- [ ] 更新 handoff buffer 路径 `.agent/context/task.md` → `.git/vibe3/handoff/<branch>/current.md`
- [ ] 移除对 `task.md` 的依赖，改用 SQLite 作为真源
- [ ] 更新相关文档引用到 v3 版本

(End of file)
