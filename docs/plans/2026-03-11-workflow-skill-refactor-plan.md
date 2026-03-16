---
document_type: plan
title: workflow skill refactor plan
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - docs/plans/2026-03-11-workflow-skill-boundary-audit.md
  - .agent/README.md
  - docs/standards/v2/skill-standard.md
  - docs/standards/v2/skill-trigger-standard.md
  - docs/standards/v2/shell-capability-design.md
  - .agent/workflows/vibe-new.md
  - .agent/workflows/vibe-start.md
  - .agent/workflows/vibe-commit.md
  - skills/vibe-commit/SKILL.md
  - skills/vibe-task/SKILL.md
  - skills/vibe-check/SKILL.md
  - skills/vibe-save/SKILL.md
  - skills/vibe-issue/SKILL.md
---

# Goal

把当前 Vibe 入口收敛为清晰的两层结构：

- `workflow` 只负责流程编排、入口语义、委托关系
- `skill` 负责具体业务逻辑、shell 调用顺序、blocker 处理与输出格式

最终避免：

- workflow 内嵌大量业务判断
- workflow/skill 双写同一套逻辑
- 缺少 skill 时 workflow 被迫兼任 skill

# Non-Goals

- 本轮不重做 shell 命令能力
- 不同时重写所有 workflow/skill
- 不修改 roadmap/task/flow 对象模型

# Design Rules

## 0. Namespace Rule

命名空间统一为：

- `workflow` 使用 `vibe:*`
- `skill` 使用 `vibe-*`

含义固定如下：

- `vibe:new` / `vibe:start` / `vibe:commit` = 入口、编排、串联
- `vibe-new` / `vibe-start` / `vibe-commit` = 具体业务逻辑、判断与操作纪律

迁移原则：

- workflow 文件的 frontmatter `name` 逐步收敛到 `vibe:*`
- `skills/*/SKILL.md` 的 `name` 保持 `vibe-*`
- 用户侧已有 `/vibe-new`、`/vibe-start` 等入口可先保留为兼容别名
- 兼容期内，文案必须明确“slash 入口触发 workflow，workflow 再委托同名 skill”

禁止继续出现以下混淆：

- workflow 与 skill 使用同名但不同层级语义
- workflow 看起来像 skill
- skill 看起来像 workflow 注册入口

## 1. Workflow 固定职责

每个 `.agent/workflows/*.md` 只允许包含四类内容：

1. 触发语义
2. 流程阶段顺序
3. 需要委托到哪个 skill / shell 能力
4. 停止点与交接点

workflow 不应包含：

- 复杂条件分支树
- 具体业务判断标准
- 具体 shell 修复策略
- 长篇 blocker 分类细则
- 与相邻 skill 的细粒度冲突裁决

一句话：

- workflow = orchestration graph

## 2. Skill 固定职责

每个 `skills/*/SKILL.md` 负责：

1. 业务判断
2. shell 调用步骤
3. blocker / fallback / handoff 处理
4. 输出结构与证据要求

skill 应承载：

- 如何判断用户处于哪个对象层级
- 何时读取哪个 shell 输出
- 如何决定下一步动作
- 如何在失败时停止或转交

一句话：

- skill = business logic + operating discipline

## 3. Shell 固定职责

shell 只负责 capability layer：

- 查询共享真源
- 原子写入
- 单一现场的确定性动作

shell 不负责：

- 任务拆分
- 优先级判断
- 是否进入下一个 workflow

# Target Architecture

## A. 健康模式模板

推荐结构如下：

### workflow

- 1. 说明这是哪个入口
- 2. 说明何时调用哪个 skill
- 3. 说明何时停下、何时切到下一个 workflow

### skill

- 1. 定义对象边界
- 2. 定义 shell 读取顺序
- 3. 定义业务判断
- 4. 定义可自动处理项 / 阻塞项 / 需用户确认项
- 5. 定义输出与 handoff

## B. 反模式模板

以下结构应视为需要整改：

- workflow 自己写完整业务判断树
- workflow 里直接定义大量 shell 调用细节
- workflow 里直接写 blocker 分类策略
- skill 与 workflow 各写一套完整流程
- workflow 没有 skill 承接，却承担复杂逻辑

## C. 语义清理检查

每次调整入口时，都必须先判断该文档究竟属于 workflow 还是 skill：

属于 `workflow` 的信号：

- 主要在描述入口触发条件
- 主要在描述阶段顺序
- 主要在描述“下一步委托谁”
- 本身不应独立完成业务判断

属于 `skill` 的信号：

- 需要解释对象边界
- 需要根据 shell 输出做判断
- 需要定义 fallback / blocker / handoff 规则
- 需要定义具体执行步骤与输出格式

若一个文件同时满足两类信号，应视为语义污染，必须拆分。

# Entry-by-Entry Refactor Plan

## Phase 1: 收敛重灾区

### 1. `vibe-new`

当前问题：

- workflow 已承担 handoff intake、task/plan/roadmap 绑定、flow/worktree 约束等业务逻辑
- 仓库内没有 `skills/vibe-new/SKILL.md`

调整目标：

- 新建 `skills/vibe-new/SKILL.md`
- 把以下内容从 workflow 下沉到 skill：
  - handoff mode 细则
  - roadmap item / task / plan intake 规则
  - task 缺失或 spec 缺失时的回退逻辑
  - flow/worktree 使用纪律
- `vibe-new.md` 只保留：
  - 这是规划入口
  - 先调度 roadmap，再委托 `vibe-new` skill
  - plan/task 绑定完成后 HARD STOP

### 2. `vibe-start`

当前问题：

- workflow 已承担 task 选择顺序、auto fallback、blocker 分类、handoff 写回逻辑
- 仓库内没有 `skills/vibe-start/SKILL.md`

调整目标：

- 新建 `skills/vibe-start/SKILL.md`
- 把以下内容从 workflow 下沉到 skill：
  - 当前 flow 如何找 task
  - spec 缺失时如何回退
  - auto 模式多 task 顺序
  - blocker 分类与 handoff 写回
- `vibe-start.md` 只保留：
  - 这是执行入口
  - 必须按 plan 执行
  - 需要时委托 `vibe-start` skill
  - 完成后转 `/vibe-commit` 或回上层入口

### 3. `vibe-commit`

当前问题：

- workflow 与 skill 同时维护较完整逻辑

调整目标：

- 保留 `skills/vibe-commit/SKILL.md` 作为完整真源
- 薄化 `.agent/workflows/vibe-commit.md`
- workflow 只保留：
  - 入口语义
  - 必须先审工作区
  - 委托 `vibe-commit` skill
  - 下一步可能去 `vibe-integrate`

## Phase 2: 清理周边入口

### 4. `.agent/README.md`

调整目标：

- 明确声明：
  - workflow = 入口 / 流程
  - skill = 业务逻辑
- 明确声明：
  - `vibe:*` = workflow namespace
  - `vibe-*` = skill namespace
- 去掉不存在的 workflow 链接
- 去掉过时命令示例

### 5. 统一 workflow 模板

建议为 `.agent/workflows/*.md` 固定模板：

1. `Input`
2. `Workflow Role`
3. `Delegation`
4. `Stop Conditions`
5. `Next Workflow`

不再在 workflow 中展开长篇业务细则。

### 6. 统一 skill 模板

建议为 `skills/*/SKILL.md` 固定模板：

1. `Overview`
2. `Object Boundary`
3. `Truth Sources`
4. `Execution Flow`
5. `Automatic vs Blocked vs Confirm`
6. `Output Contract`

# Migration Sequence

按以下顺序改，风险最低：

1. 先补 `skills/vibe-new/SKILL.md`
2. 再薄化 `.agent/workflows/vibe-new.md`
3. 再补 `skills/vibe-start/SKILL.md`
4. 再薄化 `.agent/workflows/vibe-start.md`
5. 再薄化 `.agent/workflows/vibe-commit.md`
6. 统一 workflow frontmatter/display name 到 `vibe:*`
7. 最后更新 `.agent/README.md`

原因：

- `vibe-new` / `vibe-start` 当前没有对应 skill，是边界问题最严重的入口
- `vibe-commit` 虽然双写，但至少已有 skill 承接，风险较低

# Acceptance Criteria

完成后应满足：

1. `vibe-new` / `vibe-start` 都有对应 skill
2. 任何 workflow 文件都不再独立承载复杂业务判断树
3. `vibe-commit` 只保留一套完整业务逻辑真源
4. `.agent/README.md` 与真实目录结构一致
5. workflow 之间只串联 skill / shell，不自己重写 skill 逻辑
6. workflow/skill 命名空间可一眼区分：`vibe:*` vs `vibe-*`

# Files To Modify

- `.agent/workflows/vibe-new.md`
- `.agent/workflows/vibe-start.md`
- `.agent/workflows/vibe-commit.md`
- `.agent/README.md`
- `skills/vibe-new/SKILL.md` (new)
- `skills/vibe-start/SKILL.md` (new)

# Test Command

```bash
find .agent/workflows -maxdepth 1 -type f | sort
find skills -maxdepth 2 -name 'SKILL.md' | sort
rg -n "Gate|blocker|spec_standard|spec_ref|roadmap item|handoff mode|auto 模式|Execution Loop" .agent/workflows/vibe-new.md .agent/workflows/vibe-start.md .agent/workflows/vibe-commit.md
```

人工验收：

- workflow 中只剩流程级语句
- 具体规则迁移到对应 `skills/*/SKILL.md`

# Expected Result

- 入口清晰
- 真源单一
- workflow 不再膨胀成“半个 skill”
- 后续自动化链路（`vibe-start -> vibe-task -> vibe-new -> vibe-roadmap`）可以放到 skill 层实现，而不是继续堆进 workflow

# Change Summary

- Modified: 4 files
- Added: 2 files
- Approximate lines: 180-260
