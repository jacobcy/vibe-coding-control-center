---
document_type: standard
title: Shared-State Command Standard
status: approved
scope: shared-state
authority:
  - command-semantics
  - command-boundaries
  - command-naming
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-10
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/README.md
  - docs/standards/glossary.md
  - docs/standards/data-model-standard.md
  - docs/standards/skill-standard.md
  - docs/standards/registry-json-standard.md
  - docs/standards/roadmap-json-standard.md
  - docs/standards/shell-capability-design.md
---

# 共享状态命令标准

本文档是 Vibe 共享状态命令的唯一规范真源，定义 `vibe roadmap`、`vibe task`、`vibe flow`、`vibe check` 的最终命令模型。

本文档只定义最终标准，不记录历史演进、迁移步骤、现状偏差或实现映射。

## 0. Shell Role

`vibe` Shell 的顶层定位是 capability layer，不是 workflow engine。

在共享状态命令域中，Shell 只负责暴露原子、可组合、可验证的方法，并隔离 skill 与共享状态真源。

完整的 Shell 设计原则、职责边界与审查清单，见：

- [shell-capability-design.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/shell-capability-design.md)

本文档使用的核心术语定义见：

- [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md)

命令的数据模型基础见：

- [data-model-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/data-model-standard.md)
- [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md)
- [roadmap-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/roadmap-json-standard.md)

## 1. Scope

本文档只覆盖四个共享状态命令域：

- `vibe roadmap`
- `vibe task`
- `vibe flow`
- `vibe check`

其他顶层命令不在本文档范围内。

## 1.1 Data Model Dependency

四个命令域必须建立在共享状态文件标准之上：

- `vibe roadmap` 以 `roadmap.json` 为规划态真源
- `vibe task` 以 `registry.json` 为执行态真源
- `vibe flow` 以 branch 作为开放现场锚点（解耦 `worktrees.json`），并以 `flow-history.json` 表达已关闭 flow 历史
- `vibe check` 以各层真源文件为审计对象，不自建独立业务真源

命令标准不得覆盖或重述文件级 schema；文件字段以对应数据模型标准为准。

## 2. Global Rules

### 2.1 Command Shape

- 命令格式统一为 `vibe <domain> <subcommand> [options] [args]`
- 子命令使用短单词
- 长参数统一使用 `--kebab-case`
- 查询命令优先使用 `status / list / show`
- 命令应尽量对应单一原子动作

### 2.2 Action Naming

- 向共享模型新增实体使用 `add`
- 创建运行时现场使用 `new`
- `add` 与 `new` 不能混用
- 命令名必须表达能力，不表达完整业务流程

结论：

- `roadmap add` = 新增规划项
- `task add` = 新增执行任务
- `flow new` = 创建现场

### 2.3 Output Rules

- 默认输出面向人类阅读
- 机器可读输出统一使用 `--json`
- `--json` 输出必须保持字段稳定

### 2.4 Non-Interactive Rules

- 所有命令默认非交互
- 批量、覆盖式或上下文不唯一的高风险写操作，必须显式传 `-y` 或 `--yes`
- 若命令只作用于当前现场或明确单目标，可以直接执行，但上下文不足时必须直接失败
- help 文案必须明确标出哪些子命令要求 `-y`
- 命令失败时必须暴露阻塞事实，不能擅自 fallback 到直接改数据源

### 2.5 Runtime vs Persistent State

- 运行时计算字段不得伪装成持久化真源
- 持久化数据只保存稳定共享事实
- 临时现场状态只能在查询时计算

示例：

- `dirty` 可以显示，但不能作为共享真源字段持久化
- `branch` 与 `worktree` 可以作为当前绑定事实存在，但不能作为长期历史索引

## 3. Layer Mapping

四个命令域的职责固定如下：

- `vibe roadmap` = 规划层
- `vibe task` = 执行层
- `vibe flow` = 现场层
- `vibe check` = 审计胶水层

禁止：

- 用 `roadmap` 承担执行层职责
- 用 `task` 承担规划层职责
- 用 `flow` 承担 task 生命周期或规划职责
- 用 `check` 承担业务写入职责
- 用 Shell 替 skill 承担工作流编排职责

## 3.1 Core Semantics

以下关系建立在 [glossary.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/glossary.md) 的术语定义之上。

语义关系：

- `repo issue <-> roadmap item` 多对多
- `repo issue <-> task` 多对多
- `roadmap item <-> task` 多对多
- `task <-> flow` 多对一（单个 task 在任一时刻只应绑定一个当前 flow）
- `task <-> pr` 一对一
- `milestone -> roadmap window` 一对多

补充约束：

- 默认 happy path = `repo issue -> roadmap item -> task -> flow -> PR`
- `roadmap` 负责 GitHub Project 规划对象
- `task` 只负责 execution record
- `flow` 只负责执行现场
- slash / workflow 只能调度这些对象，不得重新发明对象层级
- GitHub 官方字段与 Vibe 扩展字段可以同时同步，但语义层级必须分离

## 4. `vibe roadmap` Standard

### 4.1 Responsibility

`vibe roadmap` 只负责：

- 管 roadmap item
- 管规划优先级
- 管规划窗口锚点（含 `milestone` / `version_goal` 兼容语义）
- 管 roadmap item 与 `repo issue` / task 的映射

### 4.2 Boundaries

`vibe roadmap` 不负责：

- task 生命周期
- worktree 与 branch 现场
- PR 发布与归档
- 当前版本号真源

### 4.3 Standard Subcommands

- `status`
- `list`
- `show <roadmap-item-id>`
- `add <title>`
- `sync`
- `assign <text>`
- `classify <roadmap-item-id> --status <status>`
- `audit`
- `version <set-goal|clear-goal>`

### 4.4 Query Rules

- `status` 用于规划层概览
- `list` 用于列出 roadmap item / mirrored GitHub Project item
- `show` 用于查看单个规划项详情
- 查询类子命令支持 `--json`

`list` 支持：

- `--status <p0|current|next|deferred|rejected>`
- `--source <github|local>`
- `--keywords <text>`
- `--linked`
- `--unlinked`

### 4.5 Write Rules

以下子命令属于写操作，必须要求 `-y` 或 `--yes`：

- `add`
- `sync`
- `assign`
- `classify`
- `version set-goal`
- `version clear-goal`

写入边界：

- `add` 新增的是 roadmap item，而不是 task / flow
- `add` 必须先创建远端 GitHub Project item，再回填本地 mirror
- `sync` 只同步 GitHub Project 规划层事实，不自动创建 execution record
- `sync` 不对全部 `repo issue` 做自动 intake；不是所有 `repo issue` 都自动进入 GitHub Project
- `assign` / `classify` 只能修改 roadmap item 的规划层字段与关联
- `sync` 不同步 `task` / `flow` / execution bridge 等本地执行字段
- `sync` 不能改写 `content_type` 这类 GitHub 官方身份语义
- shell 不负责智能 intake gate；`repo issue` 是否纳入 roadmap item，属于上层 skill / workflow 的 triage 判断
- `repo issue` 真源仍在 GitHub；规划层只消费 `repo issue intake 视图`，不维护本地长期 issue registry / cache
- intake 视图应优先基于运行时查询与 roadmap mirror 对比；如需留痕，应保存 triage 决策快照而不是 issue 整池真源

### 4.6 Status and Provider Rules

规划层状态只允许：

- `p0`
- `current`
- `next`
- `deferred`
- `rejected`

其中：

- `current` 表示当前规划窗口纳入的项
- `current` 不表示某个 branch / worktree 当前正在做什么
- 分支当前焦点只能由 `flow` 与 task runtime 绑定表达
- `current` 表达的是 roadmap item 所在规划窗口，不是 execution record 当前态

provider 只允许：

- `github`
- `local`

补充约束：

- `sync` 的目标语义是对齐 local roadmap items 与 GitHub Project items
- `roadmap sync` 只负责规划层 mirror 同步，不负责 execution record 注册或 task 拆分
- `feature` / `task` / `bug` 只作为 roadmap item 的 `type`
- 若 roadmap item `type=feature`，应保持 `1 feature = 1 branch = 1 PR`
- `milestone` 是规划窗口锚点，不是 flow 切换开关
- `roadmap sync` 默认从当前 git 环境推导 repo，并从 `roadmap.json.project_id` 确定目标 project
- roadmap item 上的 `spec_standard` / `execution_record_id` / `spec_ref` / `linked_task_ids` 属于本地执行桥接字段，不写回 GitHub Project

### 4.7 Prohibited Semantics

禁止：

- 将 `openspec` 作为 roadmap provider
- 将 roadmap item 直接当作 task 使用
- 通过 `roadmap` 命令隐式创建 flow
- 通过 `roadmap sync` 自动决定 task 拆分
- 持久化 `current_version`
- 持久化 `branch`
- 持久化 `worktree`
- 持久化 `dirty`
- 将 `version bump`
- 将 `version next`
- 将 `version complete`
  当作版本真源管理动作

## 5. `vibe task` Standard

### 5.1 Responsibility

`vibe task` 只负责：

- 管 execution record 生命周期
- 管 task 与 roadmap item / `repo issue` / pr 的关联
- 管 subtasks
- 管 task 归档事实
- 管 task 当前 runtime 绑定事实

### 5.2 Boundaries

`vibe task` 不负责：

- roadmap 排布
- 规划优先级
- 现场创建与清理
- 将 `branch` / `worktree` 当作长期历史索引

补充约束：

- `task audit` 的目标语义是 execution record 审计 / 修复
- `task audit` 可以核对 OpenSpec / plans / 分支证据，但不替 `roadmap sync` 承担规划层镜像同步
- OpenSpec change / plan 文档只作为 execution spec 来源桥接，不自动变成 roadmap item

### 5.3 Standard Subcommands

- `list`
- `show <task-id>`
- `add <title>`
- `update <task-id>`
- `remove <task-id>`
- `audit`

### 5.4 Query Rules

- `list` 用于任务总览
- `show` 用于查看单个 execution record 详情
- 查询类子命令支持 `--json`

`list` 支持：

- `--status <todo|in_progress|blocked|completed|archived>`
- `--source <issue|local|openspec>`
- `--keywords <text>`

### 5.5 Write Rules

以下子命令属于写操作，必须要求 `-y` 或 `--yes`：

- `add`
- `update`
- `remove`

`update` 只允许修改执行层事实，例如：

- `--status`
- `--next-step`
- `--roadmap-item`
- `--issue-ref`
- `--pr`
- `--bind-current`
- `--unbind`

`task add/update` 可以写入的桥接关系仅限：

- `roadmap_item_ids`
- `issue_refs`
- `pr_ref`
- `spec_standard`
- `spec_ref`
- runtime 绑定事实

`task add/update` 不得承担：

- 创建 GitHub Project item
- 决定 roadmap item `type`
- 变更 milestone 或规划窗口
- 改写 GitHub Project item 的官方来源类型

### 5.6 Status and Source Rules

执行层状态只允许：

- `todo`
- `in_progress`
- `blocked`
- `completed`
- `archived`

来源只允许：

- `issue`
- `local`
- `openspec`

其中：

- `issue` source 表示该 execution record 来源于 `repo issue`
- `local` 不得被解释为 roadmap item 的替代物
- `openspec` 表示执行输入来源，不表示规划层 provider

`spec_standard` 只允许：

- `openspec`
- `kiro`
- `superpowers`
- `supervisor`
- `none`

### 5.7 Runtime Binding Rules

- task 可以记录当前绑定的 `branch`、`worktree`、`agent`
- 这些字段只表示当前 runtime 绑定
- task 完成后必须清空 runtime 绑定
- task 归档后必须清空 runtime 绑定

### 5.8 Prohibited Semantics

禁止：

- 使用 `in-progress`
- 使用 `done`
- 使用 `merged`
- 使用 `skipped`
- 用 `task` 承担 roadmap 规划职责
- 将 roadmap item `type=task` 直接等同于本地 `task`
- 用 `branch` 或 `worktree` 作为 task 历史索引

## 6. `vibe flow` Standard

### 6.1 Responsibility

`vibe flow` 只负责：

- 管逻辑 `flow` 现场
- 管当前 `branch` 的 flow 级现场动作
- 管单个 flow 的查询与开放现场大盘
- 管 flow 历史留存与 branch 关闭
- 管当前 task 的绑定与解绑
- 管当前现场的发布与检查入口

### 6.2 Boundaries

`vibe flow` 不负责：

- roadmap 查询
- task 历史归档
- 全局 task 生命周期管理
- 关闭 issue
- 合并 PR
- review / CI 失败后的自动修复
- 跨 worktree 的分支同步编排
- 将命名输入当作共享模型字段
- 并行 worktree 的物理创建与目录进入编排

### 6.3 Standard Subcommands

- `show [<flow-name>|<branch>]`
- `status`
- `list`
- `new <name>`
- `switch <name>`
- `bind <task-id>`
- `pr`
- `review`
- `done`

### 6.4 Query Rules

- `show` 用于查看单个 flow 详情，默认当前 flow
- `status` 用于查看未关闭 flow 大盘
- `list` 用于查看全部 flow，包括历史
- `review` 用于检查当前 PR 或执行本地最终审查
- 查询类子命令支持 `--json`

`show` 支持：

- `--json`

`review` 支持：

- `--local`
- `--json`

`flow` 不支持：

- `--keywords`

### 6.5 Write Rules

`vibe flow` 写操作均为当前 repo 或显式单目标动作，应保持非交互、失败即停止，不要求额外确认：

- `new`
- `switch`
- `bind`
- `pr`
- `done`

### 6.6 Naming Rules

- `new <name>`、`switch <name>` 中的 `name` 是 flow 命名输入，不定义 roadmap item、feature 或 task
- `show [<flow-name>|<branch>]` 可以接受 flow slug 或 branch ref
- `feature` 若出现，只能是 roadmap item `type=feature`，不是 flow 共享模型字段

### 6.7 Semantic Separation

- `pr` = publish
- `review` = inspect
- `show` = 单 flow 查询
- `status` = open flow dashboard
- `list` = 全量 flow 枚举
- `done` = close flow and branch, not task / issue completion

`pr` 可以有副作用，例如：

- push
- 创建或更新 PR
- CHANGELOG 相关动作
- 版本发布相关动作

`review` 默认不产生发布副作用。

### 6.8 Runtime State Rules

现场状态只允许：

- `active`
- `idle`
- `missing`
- `stale`

`dirty`：

- 可以在 `status` 或 `list` 中输出
- 只能运行时计算
- 不能作为持久化真源字段

### 6.9 Prohibited Semantics

禁止：

- 用 `flow` 描述 task 生命周期管理
- 用 `flow` 描述 roadmap 规划入口
- 将 `feature` 写成共享模型字段
- 持久化 `dirty`
- 让 `review` 默认产生发布副作用
- 通过 `flow sync` 将当前分支批量 merge 到所有 worktree 分支
- 让 `done` 自动关闭 task 或 issue
- 让 `switch` 进入已经有 PR 事实的 flow
- 让 `new` 重新创建已关闭历史中的同名 flow

## 7. `vibe check` Standard

### 7.1 Responsibility

`vibe check` 只负责：

- 聚合各层 audit
- 做跨层一致性检查
- 做通用 schema 校验
- 做文档元数据校验

### 7.2 Boundaries

`vibe check` 不负责：

- 直接实现各层完整业务逻辑
- 默认执行 fix
- 处理业务状态修改
- 替代各层自己的 audit

### 7.3 Standard Subcommands

- `check`
- `check roadmap`
- `check task`
- `check flow`
- `check link`
- `check json <file>`
- `check docs`

### 7.4 Execution Rules

- `check` 作为总入口，执行全量审计汇总
- `check roadmap` 只汇总 `roadmap audit`
- `check task` 只汇总 `task audit`
- `check flow` 只汇总 `flow audit`
- `check link` 只检查跨层链接一致性
- `check json <file>` 只做 JSON / schema 校验
- `check docs` 只做 frontmatter / 元数据审计

### 7.5 Cross-Layer Link Rules

`check link` 至少覆盖：

- roadmap item 关联不存在的 task
- task 关联不存在的 roadmap item
- task runtime 指向不存在的 worktree
- 已完成 task 仍残留 runtime 绑定

### 7.6 Output Rules

- `check` 相关子命令支持 `--json`
- 输出按域分组：
  - `roadmap`
  - `task`
  - `flow`
  - `link`
  - `docs`

每组至少包含：

- `status`
- `errors`
- `warnings`
- `summary`

### 7.7 Prohibited Semantics

禁止：

- 在 `check` 中重复实现各层完整审计逻辑
- 在 `check` 中默认执行 fix
- 在 `check` 中处理业务逻辑
- 将 `check` 扩展成第二套 workflow 系统
