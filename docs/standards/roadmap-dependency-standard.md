---
document_type: standard
title: Roadmap Dependency Standard
status: draft
scope: roadmap-planning
authority:
  - roadmap-dependency-model
  - ready-blocked-semantics
  - dependency-validation-rules
author: GPT-5 Codex
created: 2026-03-11
last_updated: 2026-03-11
related_docs:
  - SOUL.md
  - CLAUDE.md
  - docs/standards/glossary.md
  - docs/standards/data-model-standard.md
  - docs/standards/roadmap-json-standard.md
  - docs/standards/command-standard.md
---

# Roadmap Dependency Standard

本文档定义 roadmap item 依赖关系的规划层语义，回答以下问题：

- roadmap item 的依赖关系应建模在哪一层
- `ready` / `blocked` / `blockers` 应如何解释
- 依赖声明需要满足哪些最小校验规则
- 依赖语义与 task / flow / GitHub Project sync 的边界如何分离

本文档只定义 roadmap 依赖的专项规则，不替代高层共享模型标准，也不直接定义 shell 命令实现细节。

本文档涉及的 `roadmap item`、`repo issue`、`task`、`flow`、`worktree`、`branch` 等正式术语以 [glossary.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/docs/standards/glossary.md) 为准。

## 1. Scope

本文档只负责：

- roadmap item 依赖关系的规划层模型
- `ready` / `blocked` / `blockers` 的判定语义
- 依赖合法性校验规则
- 依赖语义与 roadmap sync / task runtime 的边界

本文档不负责：

- task DAG
- flow runtime 调度
- worktree 生命周期
- GitHub Project 原生关系字段的双向同步
- 自动排产或自动执行编排

## 2. Core Model

roadmap 依赖模型采用以下基础判断：

- 依赖关系只在 roadmap item 层建模
- `p0/current/next/deferred/rejected` 继续表示规划窗口
- `ready/blocked` 表示执行可达性维度，与规划窗口正交
- `blocked` 只表示规划层依赖阻塞，不等于 task 执行态 `blocked`

因此，一个 roadmap item 同时有两类状态：

- 规划窗口状态
- 依赖可达性状态

示例：

- 一个 item 可以是 `current + ready`
- 一个 item 可以是 `current + blocked`
- 一个 item 也可以是 `next + ready`

`ready/blocked` 不改变该 item 的窗口归类，只补充“当前是否具备推进条件”。

## 3. Layer Ownership

依赖语义的职责分层固定如下：

- 用户视角主链：`issue -> flow`
- 系统内部 gate 主链：`issue -> roadmap item -> dependency gate -> flow`

- `roadmap item`
  - 负责依赖声明
  - 负责 ready/blocked 的规划层解释
- `task`
  - 负责 execution record
  - 不负责作为 roadmap 依赖真源
- `flow`
  - 负责 task runtime 容器
  - 不负责表达 roadmap 的先后关系
- `roadmap sync`
  - 负责 roadmap mirror 同步
  - 不负责发明依赖调度逻辑

约束：

- 不得把 roadmap 依赖关系提前下沉到 task / flow runtime
- 不得要求 task 完成状态直接替代 roadmap item 依赖语义
- 不得把分支、worktree、PR 当作 roadmap 依赖对象
- `roadmap item` 对 gate 是真源，但对用户应尽量透明

## 4. Field Model

第一版依赖字段建议为：

- `depends_on_item_ids`

字段语义：

- `depends_on_item_ids` 是当前 roadmap item 显式依赖的其他 roadmap item 主键数组
- 数组中的每个元素都必须是合法的 `roadmap_item_id`
- 空数组表示当前 item 没有声明式前置依赖

字段约束：

- 字段落点应在 `roadmap.json.items[]`
- 字段类型必须是字符串数组
- 不允许 `null`
- 不允许重复 ID
- 不允许引用当前 item 自身

本字段只表达“前置项”，不表达：

- 执行顺序脚本
- 优先级高低
- 自动调度策略
- GitHub Project 原生 TRACKS / TRACKED_BY 身份

## 5. Computed Semantics

第一版至少定义以下派生语义：

### 5.1 `ready`

当一个 roadmap item 满足以下条件时，可视为 `ready`：

- 没有声明前置依赖
- 或者其 `depends_on_item_ids` 指向的 roadmap item 均已满足“解除阻塞”的完成条件

`ready` 是查询结果，不要求作为共享真源字段持久化。

### 5.2 `blocked`

当一个 roadmap item 满足以下条件时，可视为 `blocked`：

- 至少存在一个尚未解除阻塞的前置 roadmap item

`blocked` 同样是查询结果，不要求直接写回 roadmap item。

### 5.3 `blockers`

`blockers` 表示当前 item 仍被哪些前置 roadmap item 阻塞。

最小语义：

- `blockers` 是 `depends_on_item_ids` 的子集
- 只包含当前仍未解除阻塞的项

## 6. Unblock Rule

第一版必须显式定义“什么叫前置项已经解除阻塞”。

第一版采用强证据门禁：

- 解除依赖的唯一有效证据是依赖项对应主 PR 已 `merged`

这意味着：

- 仅有 task `completed` 不足以解除依赖
- 仅有 roadmap 本地状态更新不足以解除依赖
- 仅有 handoff、说明文字或人工口头判断不足以解除依赖

### 6.1 Dependency Evidence Rule

roadmap 依赖解除必须遵循以下规则：

- roadmap item 负责声明依赖关系
- execution layer 负责提供交付证据
- 主 PR 已 merged 是解除依赖的唯一有效证据
- 无 `pr_ref` 或 `pr_ref` 对应 PR 未 merged，依赖不得解除

### 6.2 Governance Gap Rule

若某个依赖项在业务上声称“已完成”，但没有 merged PR 证据，则该项不算已解除阻塞，而应视为治理缺口。

默认动作：

- 先补 `pr_ref`
- 或补齐 task / PR bridge
- 或补齐缺失的交付证据

在证据补齐前：

- 当前 item 继续视为 `blocked`
- 不得进入 `ready`
- 不得继续放行到下游 task / flow

## 7. Validation Rules

第一版最小校验规则包括：

### 7.1 Existence

- `depends_on_item_ids` 中引用的 roadmap item 必须存在

### 7.2 Self Dependency

- 不允许 item 依赖自己

### 7.3 Duplicate Dependency

- 不允许同一个依赖 ID 在同一数组中重复出现

### 7.4 Cycle

- 不允许形成环
- 第一版至少应覆盖直接环与简单间接环
- 若成本可控，优先直接做通用无环校验

### 7.5 Cross-Layer Reference

禁止把以下对象写入 `depends_on_item_ids`：

- task_id
- branch
- worktree_name
- pr_ref
- repo issue ref

## 8. Query Surface Contract

后续查询面允许暴露以下能力：

- `roadmap list`
  - 按 `ready` / `blocked` 过滤或分组
- `roadmap show`
  - 展示 `depends_on_item_ids`
  - 展示当前 `blockers`
  - 展示 blocker 缺失的是哪一类证据，例如 `missing_pr_ref` / `pr_not_merged`
- `roadmap status`
  - 汇总 ready/blocked 数量

约束：

- 查询结果可以包含派生字段
- 派生字段不要求持久化回 `roadmap.json`
- 查询结果的口径必须引用本文档，而不是由各命令单独发明

## 9. Flow Gate Contract

依赖证据门禁最终必须落在 flow 准入层，而不是只停留在查询提示层。

第一版至少有两个硬门禁入口：

- `flow new`
- `flow bind issue`

规则如下：

- 任何会把 roadmap item / issue 推进为可执行 flow 的入口，都必须执行依赖证据校验
- 若依赖项缺少 merged PR 证据，则必须直接阻断
- 阻断结果必须输出明确 blocker 与缺失证据类型

约束：

- 只做 `roadmap list/show/status` 的提示不足以约束 agent
- 只拦一个 flow 入口会留下绕过路径
- 第一版不应提供“跳过依赖 gate”的软开关

## 10. Sync Boundary

第一版同步边界固定如下：

- 本地 roadmap mirror 是依赖真源
- `roadmap sync` 首版不要求把依赖关系映射到 GitHub Project 原生关系字段
- 如果未来要映射 GitHub Project 原生关系，必须作为独立后续阶段定义

这意味着：

- 依赖能力的第一版可先完全在本地规划层落地
- 不能因为 GitHub Project 原生字段暂未纳入，就阻断本地依赖能力

## 11. Prohibited Semantics

禁止：

- 把 roadmap 依赖标准写成 task runtime 标准
- 把 `blocked` 直接等同于 task 执行态 `blocked`
- 把 roadmap item 依赖关系降格为 branch 依赖或 worktree 依赖
- 把 GitHub Project 当前没有承载的关系字段伪装成第一版必需能力
- 在未定义解除阻塞规则前，直接把 `ready` 持久化成真源字段
- 把 roadmap 依赖标准扩展成完整 DAG 调度器规范
- 用 task `completed`、roadmap 本地状态或人工说明替代 merged PR 证据
- 只在单一 flow 入口做门禁，导致其他入口可以绕过依赖约束

## 12. Future Extensions

本文档允许后续扩展，但必须独立评估：

- GitHub Project 原生关系字段映射
- 更复杂的 blocker 分类
- 自动推荐下一批 ready items
- 与 milestone / version window 的组合查询

这些扩展在进入标准前，不得提前写成默认语义。
