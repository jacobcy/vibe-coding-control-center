---
document_type: standard
title: Shared-State Command Standard (v3)
status: approved
scope: shared-state
authority:
  - command-semantics
  - command-boundaries
  - command-naming
author: Vibe Team
created: 2026-03-24
last_updated: 2026-04-01
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/README.md
  - docs/standards/glossary.md
  - docs/standards/issue-standard.md
  - docs/standards/roadmap-label-management.md
  - docs/standards/v3/handoff-store-standard.md
---

# 共享状态命令标准 (v3 Python 版)

本文档是 Vibe 3.0 共享状态命令的现行规范真源。

旧文档 [docs/standards/vibe3-command-standard.md](../vibe3-command-standard.md)、[docs/standards/vibe3-state-sync-standard.md](../vibe3-state-sync-standard.md) 与 [docs/standards/vibe3-user-guide.md](../vibe3-user-guide.md) 仅保留为废弃目录页，不再承载规范正文。

## 0. CLI 定位

`vibe3` 在共享状态域中的职责是：

- 维护本地最小运行时事实
- 读取并聚合当前 execution scene
- 记录 events 与 handoff 上下文
- 在 `git` / `gh` 没有覆盖的本地绑定场景下提供补充能力

`vibe3` 不应重新包装以下能力：

- branch 的创建、切换、删除、merge
- GitHub issue / PR 的常规远端写操作
- roadmap / project 字段的常规远端写操作

默认原则：

- branch 生命周期优先直接使用 `git`
- issue / PR / project 的远端事实读取与写入优先直接使用 `gh`
- 本地 SQLite 只保存最小运行时绑定事实，不持久化远端展示字段

## 1. 范围

本文档只覆盖共享状态域的现行公共调用面：

- `vibe3 flow`
- `vibe3 status`
- `vibe3 check`
- `vibe3 handoff`

其中：

- `roadmap` 是规划概念，默认通过 GitHub / `gh` 管理
- `task` 是 execution bridge 语义，不再对应独立公共顶层 CLI

## 2. 真源与本地事实

共享状态域的真源与本地事实约束如下：

- Git branch、GitHub issue、GitHub PR、GitHub Project 是外部事实真源
- `flow_state.branch` 是本地 execution scene 的锚点
- `flow_issue_links` 是 issue 与 flow 关系的本地最小真源
- `handoff` 与 `events` 是本地协作增强，不替代远端业务事实

禁止：

- 将远端 issue / PR / project 展示字段长期落地为本地真源
- 用本地缓存覆盖 `git` / `gh` 已确认的远端事实
- 通过查询命令隐式扩张本地状态

## 3. 现行公共命令面

### 3.1 `vibe3 flow`

现行公共子命令只有：

- `update`
- `bind`
- `blocked`
- `show`
- `status`

明确不再作为现行公共命令面的旧入口：

- `flow add`
- `flow create`
- `flow new`
- `flow switch`
- `flow list`
- `flow done`
- `flow aborted`
- `task show`
- `task list`
- `task status`

### 3.2 `vibe3 status`

`status` 是项目特有的总览入口，用于：

- 汇总活跃 flow
- 汇总 orchestra 状态
- 补充当前仓库的 worktree / flow / issue 绑定上下文

### 3.3 `vibe3 handoff`

`handoff` 是本地协作增强入口，用于：

- 记录 plan / report / audit handoff
- 追加轻量上下文消息
- 展示当前 branch 的 handoff 链路

### 3.4 `vibe3 check`

`check` 是一致性与审计入口，用于：

- 校验 handoff store / shared-state 一致性
- 暴露缺失或冲突事实
- 做最小、显式的审计补充

`check` 不是 branch / PR / issue 生命周期包装器。

## 4. `flow` 语义边界

### 4.1 `flow update`

`flow update` 只负责：

- 为当前 branch 或显式 branch 注册 / 更新本地 flow 元数据
- 写入本地最小 execution scene 字段

`flow update` 不负责：

- 创建分支
- 切换分支
- 删除分支
- 合并 PR

这些动作应直接使用 `git` / `gh`。

### 4.2 `flow bind`

`flow bind` 是 issue 与 flow 关系的唯一公共写入口。

现行契约：

- `vibe3 flow bind <issue> [<issue> ...] [--role <role>] [--branch <branch>]`
- issue 支持数字或 GitHub URL
- `--branch` 只允许绑定到已注册、非保护的 flow 分支
- role 只允许 `task` / `related` / `dependency`

`flow bind` 只写入本地关系事实，不应扩张为远端 issue 管理包装器。

### 4.3 `flow blocked`

`flow blocked` 只负责：

- 标记本地 flow 为 blocked
- 记录阻塞原因
- 可选补充 dependency 关系

若存在远端标签同步，它只是兼容性副作用，不构成共享状态域的首要语义。

### 4.4 `flow show` / `flow status`

这两个命令是读取入口：

- `flow show`：查看单个 flow 的 execution scene
- `flow status`：查看 flow 总览

读取规则：

- 优先读取本地最小运行时事实
- 需要时按需 hydrate GitHub issue / PR 信息
- 不把远端展示字段持久化成长期本地真源

## 5. `status` 与 `gh` 的分工

`vibe3 status` 保留的原因是它提供了 `gh` 没有的项目内聚合视图。

它负责：

- flow / issue / orchestra / worktree 的联合总览

它不负责：

- 远端 issue 详情查询
- 远端 PR 详情查询
- 远端 issue / PR 写操作

因此：

- 查看 issue 详情、评论、搜索：优先使用 `gh issue`
- 查看 PR 详情、检查项、评论：优先使用 `gh pr`

## 6. `handoff` 与 `events`

`handoff` 与 `events` 属于本地增强层。

它们负责：

- 记录 plan / report / audit 的责任链
- 保留 agent 交接所需的轻量上下文
- 让 execution scene 在本地可追踪、可恢复

它们不负责：

- 充当业务真源
- 替代 GitHub issue / PR 的远端事实
- 决定 branch / PR / issue 生命周期

## 7. 现行参数规范

### 7.1 `flow update`

```bash
vibe3 flow update [<branch>] [--name <slug>] [--actor <actor>] [--spec <spec-ref>]
```

约束：

- `<branch>` 省略时默认当前分支
- 只更新本地 flow scene

### 7.2 `flow bind`

```bash
vibe3 flow bind <issue> [<issue> ...] [--role <role>] [--branch <branch>]
```

约束：

- `<issue>` 为必填
- `--branch` 省略时默认当前分支
- 显式 `--branch` 只允许已注册且非保护的 flow 分支

### 7.3 `flow blocked`

```bash
vibe3 flow blocked [--branch <branch> | --pr <pr>] [--reason <text>] [--task <issue> | --by <issue>]
```

约束：

- 目标 flow 必须已存在
- `--branch` 与 `--pr` 互斥

### 7.4 `flow show`

```bash
vibe3 flow show [--branch <branch>] [--snapshot] [--json]
```

### 7.5 `flow status`

```bash
vibe3 flow status [--all] [--json]
```

### 7.6 `status`

```bash
vibe3 status [--all] [--json]
```

## 8. 禁止语义

禁止：

- 用 `flow` 描述 branch 创建 / 切换 / 合并 / 删除
- 用 `flow` 描述 issue / PR 的常规远端写操作
- 让 `task` 重新膨胀成独立公共顶层 CLI
- 让旧命令面继续以 Active / approved 形式承载现行语义
- 用本地 sync / mirror 替代 `gh` 的直接读取与写入

## 9. 文档治理

旧文档可保留为目录页，但必须满足：

- 明确标注 deprecated
- 不再承载规范正文
- 直接指向本文件与其他现行标准

当前共享状态域的现行阅读顺序：

1. [docs/standards/v3/command-standard.md](command-standard.md)
2. [docs/standards/v3/handoff-store-standard.md](handoff-store-standard.md)
3. [docs/standards/issue-standard.md](../issue-standard.md)
4. [docs/standards/roadmap-label-management.md](../roadmap-label-management.md)
