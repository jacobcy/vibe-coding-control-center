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
last_updated: 2026-03-24
related_docs:
  - SOUL.md
  - CLAUDE.md
  - STRUCTURE.md
  - docs/README.md
  - docs/standards/glossary.md
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/skill-standard.md
  - docs/standards/v3/python-capability-design.md
---

# 共享状态命令标准 (v3 Python 版)

本文档是 Vibe 3.0 共享状态命令的唯一规范真源，定义 `vibe3 flow`、`vibe3 check`、`vibe3 status` 的最终命令模型，并约束 `roadmap` / `task` 作为概念层的使用边界。

本文档只定义最终标准，不记录历史演进、迁移步骤、现状偏差或实现映射。

## 0. Python CLI Role

`vibe3` CLI 的顶层定位是 capability layer，不是 workflow engine。

在共享状态命令域中，CLI 只负责暴露原子、可组合、可验证的方法，并隔离 skill 与共享状态真源。

补充原则：

- 读优先：先确认现场，再决定是否需要任何写操作
- 远端真源不落地：除本地运行时绑定外，不长期持久化 GitHub / GitHub Project 远端字段
- 原生命令优先：若 git / gh 已能稳定表达该动作，不新增平行包装命令

完整的 CLI 设计原则、职责边界与审查清单，见：

- [python-capability-design.md](python-capability-design.md)

本文档使用的核心术语定义见：

- [glossary.md](glossary.md)

命令的数据模型基础见：

- [data-model-standard.md](data-model-standard.md)

## 1. Scope

本文档只覆盖两个共享状态命令域和一个统一总览入口：

- `vibe3 flow`
- `vibe3 check`
- `vibe3 status`

`roadmap` 与 `task` 仍是正式概念，但不再默认对应独立公共顶层命令面。

其他顶层命令不在本文档范围内。

## 1.1 Data Model Dependency

两个命令域和统一总览入口必须建立在共享状态数据库标准之上：

- `vibe3 flow` 以 branch 作为开放现场锚点，以 SQLite `flow_state` 表为核心真源
- `vibe3 check` 以各层真源文件为审计对象，不自建独立业务真源
- `vibe3 status` 聚合 orchestra 快照与 flow 视图，不新增独立业务真源

补充说明：

- `task` 执行桥接语义以 SQLite `flow_issue_links` 表为 issue 关联真源，由 `flow bind`、`flow show`、`flow status`、`status` 暴露

**v3 架构核心**:
- SQLite 是本地缓存，GitHub 是真源
- `branch` 是 PRIMARY KEY，`flow_slug` 是显示名称
- 所有命令按 `branch` 查询，不支持按 `flow_slug` 查询
- 本地只保留运行时必须的绑定事实，不持久化远端展示字段

补充约束：

- GitHub Project 当前只按规划层事实的即时读取 / 投影视图理解，不承担 execution gate
- SQLite 数据可以从 GitHub 重建，本地只保留运行时必要的状态

命令标准不得覆盖或重述数据库级 schema；表字段以对应数据模型标准为准。

## 2. Global Rules

### 2.1 Command Shape

- 命令格式统一为 `vibe3 <domain> <subcommand> [options] [args]`
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

- `flow new` = 创建现场
- 规划层新增 / 分类 / 标注优先使用 `gh` / GitHub 原生命令

### 2.3 Output Rules

- 默认输出面向人类阅读
- 机器可读输出统一使用 `--json`
- `--json` 输出必须保持字段稳定
- 支持 `--yaml` 作为替代机器可读格式

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

两个命令域、一个总览入口与两个概念层的职责固定如下：

- `vibe3 flow` = 现场层
- `vibe3 check` = 审计胶水层
- `vibe3 status` = 总览层
- `roadmap` = 规划层（优先使用 GitHub / gh 原生命令和 skill 编排）
- `task` = 内部 execution bridge 语义

禁止：

- 用 `roadmap` 承担执行层职责或重新膨胀出独立公共写命令面
- 用 `task` 承担规划层职责或重新膨胀成独立公共 CLI
- 用 `flow` 承担 task 生命周期或规划职责
- 用 `check` 承担业务写入职责
- 用 CLI 替 skill 承担工作流编排职责
- 对 git / gh 已能稳定完成的远端写操作再包装一层自定义命令

## 3.1 Core Semantics

以下关系建立在 [glossary.md](glossary.md) 的术语定义之上。

语义关系：

- `repo issue <-> roadmap item` 多对多
- `repo issue <-> task` 多对多
- `roadmap item <-> task` 多对多
- `task <-> flow` 多对一（单个 task 在任一时刻只应绑定一个当前 flow）
- `task <-> pr` 一对一
- `milestone -> roadmap window` 一对多

补充约束：

- 用户主视角主链 = `repo issue -> flow -> plan/spec -> commit -> PR -> done`
- 内部桥接链 = `repo issue -> roadmap item -> task -> flow`
- `roadmap` 负责 GitHub Project 规划对象
- `task` 只负责 execution record / execution bridge
- `flow` 只负责执行现场
- 若一个 task 在多个 `issue_refs` 中已有明确主闭环 issue，则该角色称为 `task issue`
- `roadmap item` 是 planning 中间层，不是用户默认第一锚点
- slash / workflow 只能调度这些对象，不得重新发明对象层级
- GitHub 官方字段与 Vibe 扩展字段可以同时同步，但语义层级必须分离

## 4. `roadmap` Planning Surface Standard

### 4.1 Responsibility

`roadmap` 规划层只负责：

- 管 roadmap item
- 管规划优先级
- 管规划窗口锚点（含 `milestone` / `version_goal` 兼容语义）
- 管 roadmap item 与 `repo issue` / task 的映射

### 4.2 Boundaries

规划层不负责：

- task 生命周期
- worktree 与 branch 现场
- PR 发布与归档
- 当前版本号真源
- 在本地长期存储远端 issue / project 展示字段
- 为 GitHub / GitHub Project 写操作新增一套平行于 `gh` 的包装命令

### 4.3 Preferred Surface

当前推荐调用面：

- 远端规划读取：`gh issue list`、`gh issue view`、`gh project` 相关原生命令
- 本地现场确认：`vibe3 status`、`vibe3 flow show`
- 规划决策编排：skill / workflow

新增公共 `roadmap` 写命令前，必须先证明：

- `gh` / GitHub 原生命令无法稳定完成该动作
- 该动作同时需要维护本地最小绑定真源
- 不是单纯的便利包装

### 4.4 Query Rules

- 规划层查询优先走 GitHub / `gh` 原生命令
- 如需结合当前执行现场，使用 `vibe3 status`、`vibe3 flow show` 做本地补充确认
- 查询类能力应以只读为默认，不因查询而回填本地缓存

### 4.5 Write Rules

规划层写操作默认优先使用 `gh` / GitHub 原生命令直接完成，例如：

- label 调整
- milestone 调整
- project item 字段修改

写入边界：

- 本地 CLI 不为这些远端写操作新增平行包装，除非存在明确缺口
- skill 可以编排 `gh` 写操作，但不应把远端字段回填成长期本地缓存
- 若动作本质上只是 git / gh 已有能力，优先直接使用原生命令
- 本地持久化只允许保留最小运行时绑定事实，不为规划层写路径扩张真源

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

补充约束：

- `feature` / `task` / `bug` 只作为 roadmap item 的 `type`
- 若 roadmap item `type=feature`，应保持 `1 feature = 1 branch = 1 PR`
- `milestone` 是规划窗口锚点，不是 flow 切换开关
- roadmap 相关远端事实默认按需读取，不要求先做本地 mirror/sync
- roadmap item 上的 `spec_standard` / `execution_record_id` / `spec_ref` / `linked_task_ids` 属于本地执行桥接字段，不写回 GitHub Project

### 4.7 Prohibited Semantics

禁止：

- 将 `openspec` 作为 roadmap provider
- 将 roadmap item 直接当作 task 使用
- 通过规划层命令隐式创建 flow
- 通过本地 sync/mirror 自动决定 task 拆分
- 持久化 `current_version`
- 持久化 `branch` 作为历史索引
- 持久化 `worktree` 作为历史索引
- 持久化 `dirty`
- 将 `version bump`
- 将 `version next`
- 将 `version complete`
  当作版本真源管理动作

## 5. `task` Execution Bridge Semantics

### 5.1 Positioning

`task` 仍然是执行层术语，但当前标准不再保留独立公共 `vibe3 task` 顶层命令。

当前公共调用面统一收敛为：

- `vibe3 flow bind <issue> --role task|related|dependency`：写入 task 绑定关系
- `vibe3 flow show [--branch <branch>]`：查看当前 flow 绑定的 task issue、相关 issue、milestone 与执行上下文
- `vibe3 flow status` / `vibe3 status`：查看总览，替代旧的 task list 视角

### 5.2 Boundaries

`task` 语义仍然不负责：

- roadmap 排布
- 规划优先级
- 现场创建与清理
- 将 `branch` / `worktree` 当作长期历史索引

补充约束：

- `task` 是 execution bridge，不是独立规划对象
- `task issue` 仍表示当前 flow 的主闭环 issue 角色
- 旧文档中的 `task show` / `task list` / `task status` 视为历史调用面，不再作为现行标准

## 6. `vibe3 flow` Standard

### 6.1 Responsibility

`vibe3 flow` 只负责：

- 管逻辑 `flow` 现场
- 管当前 `branch` 的 flow 级现场动作
- 管单个 flow 的查询与开放现场大盘
- 管 flow 历史留存与 branch 关闭
- 管当前 task 的绑定与解绑
- 管当前现场的发布与检查入口

### 6.2 Boundaries

`vibe3 flow` 不负责：

- roadmap 查询
- task 历史归档
- 全局 task 生命周期管理
- 关闭 issue
- 合并 PR
- review / CI 失败后的自动修复
- 跨 worktree 的分支同步编排
- 将命名输入当作共享模型字段
- 并行 worktree 的物理创建与目录进入编排
- 对 git / gh 已能稳定完成的远端写操作做平行包装

### 6.3 Standard Subcommands

- `show [--branch <branch>]`
- `status`
- `list`
- `new <name>`
- `switch --branch <branch-or-slug>`
- `bind <issue>`
- `pr`
- `review`
- `done`
- `blocked`
- `aborted`

### 6.4 Query Rules

- `show` 用于查看单个 flow 详情，默认当前 flow
- `status` 用于查看未关闭 flow 大盘
- `list` 用于查看全部 flow，包括历史
- `review` 用于检查当前 PR 或执行本地最终审查
- 查询类子命令支持 `--json`

`show` 支持：

- `--branch` / `-b`: 指定分支名（可选，默认当前分支）
- `--snapshot`: 静态快照模式
- `--json`

`review` 支持：

- `--local`
- `--json`

`flow` 不支持：

- `--keywords`

### 6.5 Write Rules

`vibe3 flow` 写操作均为当前 repo 或显式单目标动作，应保持非交互、失败即停止，不要求额外确认：

- `new`
- `switch`
- `bind`
- `pr`
- `done`
- `blocked`
- `aborted`

补充约束：

- `flow` 写操作只应覆盖本地 runtime scene 与最小绑定事实
- 若动作本质是远端 git / gh 写操作，且不涉及本地绑定真源维护，应优先直接使用原生命令

### 6.6 Naming Rules

- `new <name>` 中的 `name` 是 flow 命名输入，不定义 roadmap item、feature 或 task
- `switch --branch <branch-or-slug>` 使用 `--branch` 选项指定目标分支或 flow slug
- `show --branch <branch>` 使用 `--branch` 选项指定分支名（可选，默认当前分支）
- `feature` 若出现，只能是 roadmap item `type=feature`，不是 flow 共享模型字段
- `bind <issue>` 中的 `issue` 支持数字或完整 GitHub URL

### 6.7 Semantic Separation

- `pr` = publish
- `review` = inspect
- `show` = 单 flow 查询
- `status` = open flow dashboard
- `list` = 全量 flow 枚举
- `done` = close flow and branch, not task / issue completion
- `blocked` = mark flow as blocked with optional dependency
- `aborted` = mark flow as aborted and cleanup

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

flow 生命周期状态 (`flow_status`)：

- `active` = 进行中
- `done` = 已完成（PR merged）
- `blocked` = 被阻塞
- `aborted` = 已中止

`dirty`：

- 可以在 `status` 或 `list` 中输出
- 只能运行时计算
- 不能作为持久化真源字段

### 6.9 Flow 创建与绑定

`vibe3 flow new` 参数：

```bash
vibe3 flow new [name] [--issue <issue>] [--branch <ref>] [--save-unstash]
```

- `name`: Flow 显示名称（可选，默认从 branch 生成）
- `--issue`: Issue number，绑定为 task issue（可选，支持数字或 URL）
- `--branch`: 起点分支（可选，默认：origin/main）
- `--save-unstash`: 将当前未提交改动带入新分支（可选）

`vibe3 flow bind` 参数：

```bash
vibe3 flow bind <issue> [--role <role>] [--branch <branch>]
```

- `issue`: Issue number (or URL)（必需）
- `--role`: Issue role（可选，默认 "task"，可选 task/related/dependency）
- `--branch`: Branch name（可选，默认当前分支；仅允许已注册的非保护 flow 分支）

### 6.10 Prohibited Semantics

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

## 7. `vibe3 check` Standard

### 7.1 Responsibility

`vibe3 check` 只负责：

- 聚合各层 audit
- 做跨层一致性检查
- 做通用 schema 校验
- 做文档元数据校验

### 7.2 Boundaries

`vibe3 check` 不负责：

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

## 8. Handoff 命令标准

### 8.1 handoff plan

```bash
vibe3 handoff plan <plan_ref> [--next-step <text>] [--blocked-by <text>] [--actor <actor>]
```

**参数**:
- `plan_ref`: Plan 文档引用（必需）
- `--next-step`: 下一步建议（可选）
- `--blocked-by`: 阻塞原因（可选）
- `--actor`: Actor 标识（可选，默认 "unknown"）

**行为**:
- 更新 flow_state.plan_ref
- 更新 flow_state.planner_actor
- 更新 flow_state.next_step
- 更新 flow_state.blocked_by
- 添加 handoff_plan 事件

### 8.2 handoff report

```bash
vibe3 handoff report <report_ref> [--next-step <text>] [--blocked-by <text>] [--actor <actor>]
```

**参数**:
- `report_ref`: Report 文档引用（必需）
- `--next-step`: 下一步建议（可选）
- `--blocked-by`: 阻塞原因（可选）
- `--actor`: Actor 标识（可选，默认 "unknown"）

**行为**:
- 更新 flow_state.report_ref
- 更新 flow_state.executor_actor
- 更新 flow_state.next_step
- 更新 flow_state.blocked_by
- 添加 handoff_report 事件

### 8.3 handoff audit

```bash
vibe3 handoff audit <audit_ref> [--next-step <text>] [--blocked-by <text>] [--actor <actor>]
```

**参数**:
- `audit_ref`: Audit 文档引用（必需）
- `--next-step`: 下一步建议（可选）
- `--blocked-by`: 阻塞原因（可选）
- `--actor`: Actor 标识（可选，默认 "unknown"）

**行为**:
- 更新 flow_state.audit_ref
- 更新 flow_state.reviewer_actor
- 更新 flow_state.next_step
- 更新 flow_state.blocked_by
- 添加 handoff_audit 事件

### 8.4 handoff append

```bash
vibe3 handoff append <message> [--kind <kind>] [--actor <actor>]
```

**参数**:
- `message`: Handoff 更新消息（必需）
- `--kind`: 更新类型（可选，默认 "note"）
- `--actor`: Actor 标识（可选，默认 "unknown"）

**行为**:
- 更新 flow_state.latest_actor
- 追加消息到当前 handoff 文档

## 9. PR 命令标准

### 9.1 pr create

```bash
vibe3 pr create -t <title> [-b <body>] [--base <branch>]
```

**Metadata 自动读取**:
- 不需要用户手动指定 task、flow、spec、planner、executor、reviewer
- 系统自动从当前 flow_state 读取：
  - `task_issue_number` → Task issue
  - `flow_slug` → Flow
  - `spec_ref` → Spec reference
  - `planner_actor` → Planner agent
  - `executor_actor` → Executor agent
  - `reviewer_actor` → Reviewer agent
- 当存在非默认 actor 时，自动生成 **Contributors** 区块（去重 + 过滤 unknown/system/server）

**行为**:
- 从当前分支创建 draft PR
- 自动在 PR body 中添加 Vibe3 Metadata 章节
- 更新 flow_state.pr_number
- 添加 pr_draft 事件

### 9.2 pr show

```bash
vibe3 pr show [PR_NUMBER] [-b <branch>]
```

**智能查找**:
1. 如果未提供 pr_number 和 branch：
   - 先从当前 flow_state 查找 pr_number
   - 如果找到，自动使用该 PR
   - 如果未找到，使用当前分支名查询
2. 如果提供 pr_number：直接查询该 PR
3. 如果提供 branch：查询该分支的 PR

**行为**:
- 显示 PR 基本信息（标题、状态、链接等）
- 如果提供了 pr_number，自动执行 change analysis

### 9.3 pr ready

```bash
vibe3 pr ready PR_NUMBER [-y]
```

**质量门禁检查**:
1. **覆盖率检查**（分层覆盖率统计）
2. **风险评分检查**（来自 inspect pr）

**行为**:
- 将 draft PR 标记为 ready for review
- 执行质量门禁检查（除非使用 --yes）
- 更新 flow_state 添加 pr_ready 事件

## 10. Design Principles

### 10.1 Architecture Principles

1. **单一真源**: GitHub 是真源，SQLite 是缓存
2. **不包装 gh**: 不简单包装 `git/gh` 已有的命令
3. **不做第二真源**: 避免与 GitHub 状态冲突

### 10.2 Naming Principles

1. **统一命名**: 相同概念使用相同术语
2. **语义清晰**: 参数名反映实际含义
3. **用户友好**: 支持便捷输入方式（如 URL 复制）

### 10.3 Responsibility Separation

1. **flow 命令**: Flow 生命周期管理
2. **task 命令**: Issue 关联和 Project 管理
3. **避免重叠**: 明确每个命令的职责边界

### 10.4 Data Model Core

**v3 架构核心**:

```
SQLite (本地缓存)                 GitHub (真源)
├── flow_state                   ├── Issues (真源)
│   ├── branch (PK)              │   └── 所有 issue 都是 GitHub issue
│   ├── flow_slug                │
│   ├── task_issue_number        └── Projects (真源)
│   ├── pr_number                    └── Project items
│   ├── flow_status
│   ├── project_item_id
│   └── project_node_id
│
└── flow_issue_links (唯一真源)
    ├── branch
    ├── issue_number
    └── issue_role (task/related/dependency)
```

**重要**:
- `branch` 是 PRIMARY KEY，`flow_slug` 是显示名称
- 所有命令都按 `branch` 查询，不支持按 `flow_slug` 查询
- Issue Role 是**关系语义**，不是 issue 的类型属性
- 同一个 issue 可以在不同的 flow 中有不同的 role

## 11. Related Documentation

- [glossary.md](glossary.md) - 术语定义
- [data-model-standard.md](data-model-standard.md) - 数据模型标准
- [python-capability-design.md](python-capability-design.md) - Python CLI 能力设计
- [vibe3-user-guide.md](../vibe3-user-guide.md) - 用户操作指南
