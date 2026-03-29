---
document_type: plan
title: Issue 333 GitHub-as-Truth Migration Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-29
last_updated: 2026-03-29
related_docs:
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/command-standard.md
  - docs/standards/vibe3-command-standard.md
  - docs/standards/vibe3-user-guide.md
related_issues:
  - gh-333
---

# Issue 333 分布实施计划：FlowState 收敛到 GitHub 真源优先

> For Agent: 先做读路径收敛，再做写路径收敛；每个阶段都必须可回滚、可验证。

## Goal

将 `src/vibe3` 的 flow/task/PR 数据边界收敛为：

- GitHub 真源字段实时读取，不再依赖本地 SQLite 回填同步
- SQLite 仅保留运行时执行现场与最小离线索引
- 去掉 `check --init/--fix` 中“补真源数据”的职责

## Problem Summary

当前 `flow_state` 存储了大量可从 GitHub 实时读取的字段，导致：

1. 本地-远端状态漂移，需要额外同步补丁（`check --init`、`check --fix`）。
2. 命令读路径不统一：部分读本地缓存，部分读远端，行为难预测。
3. 用户感知问题：远端字段（如 title/body）在降级路径下表现不一致，且 `task show` 目前未渲染 remote body。

## Scope

### In Scope

- `flow show/status`、`task show`、`pr show` 的远端事实读取收敛
- `flow_state` 真源字段停写与 schema 收缩
- `check --init/--fix` 语义重定义（只修本地结构，不回填远端真源字段）
- 文档标准与用户指南同步

### Out of Scope

- 不重写 flow 生命周期状态机
- 不引入新的 GitHub 领域对象
- 不改变 issue role 语义（`flow_issue_links` 仍为关系真源）

## Data Boundary（目标态）

### 本地保留（运行时现场）

- `branch`, `flow_slug`, `flow_status`
- `spec_ref`, `plan_ref`, `report_ref`, `audit_ref`
- `planner_*`, `executor_*`, `reviewer_*`, `latest_actor`
- `next_step`, `blocked_by`
- `planner_status`, `executor_status`, `reviewer_status`, `execution_*`

### 远端真源（查询时实时读取）

- PR 事实：`pr_number`, `pr_ready_for_review`, PR state/title/url
- Project truth：`title`, `body`, `status`, `priority`, `assignees`

### 兼容过渡字段（阶段性）

- `project_item_id`, `project_node_id` 先保留读兼容，后续评估是否彻底移除

## Delivery Map（分布实施）

### Stream A（读路径收敛，优先交付）

目标：先让用户看到的一致性恢复，避免“远端真源但展示缺失”。

1. 建立统一投影读取层（local + remote）。
2. `task show` 补齐 remote `body` 渲染。
3. `flow show/status` 与 `pr show` 统一使用投影层读取远端事实。

文件范围：

- `src/vibe3/services/flow_service.py`
- `src/vibe3/services/task_bridge_lookup.py`
- `src/vibe3/commands/task.py`
- `src/vibe3/commands/flow_status.py`
- `src/vibe3/services/pr_query_usecase.py`

验收：

- 在线模式下，`task show` 始终显示 remote title/body（若远端返回）。
- 离线模式下，清晰标注 offline，不伪造远端字段。

---

### Stream B（写路径收敛，停写真源字段）

目标：阻断“本地写真源字段”的新增漂移来源。

1. 缩减 `update_flow_state` 允许字段，分层白名单（runtime-only vs transitional）。
2. 将 PR/Project 真源字段写入改为“只读投影”，停写本地缓存。
3. 对仍需兼容读取的字段保留 backward-compat 读路径。

文件范围：

- `src/vibe3/clients/sqlite_client.py`
- `src/vibe3/services/pr_service.py`
- `src/vibe3/services/task_bridge_mutation.py`
- `src/vibe3/services/flow_create_decision.py`

验收：

- 常见命令链路中不再新增写入 `pr_number/pr_ready_for_review`。
- 功能行为不因“停写真源字段”发生回归。

---

### Stream C（check 语义重构）

目标：`check` 只做一致性审计与本地结构修复，不再承担真源回填。

1. `check --fix` 移除 `pr_number` 回填逻辑。
2. `check --init` 移除远端扫描回填 `task_issue_number` 职责。
3. 错误文案改为“请检查绑定/网络/权限”，不提示“回填数据库真源字段”。

文件范围：

- `src/vibe3/services/check_service.py`
- `src/vibe3/services/check_remote_index_mixin.py`
- `src/vibe3/commands/check.py`

验收：

- `check` 不再修改远端真源派生字段。
- `check` 输出语义与 GitHub-as-truth 一致。

---

### Stream D（Schema 收缩与文档收口）

目标：完成技术债闭环，避免旧字段继续被误用。

1. 收缩 `flow_state` schema 与 migration 路径。
2. 删除过时注释、规范中与现状冲突的字段定义。
3. 同步 `vibe3-command-standard` / `vibe3-user-guide`。

文件范围：

- `src/vibe3/clients/sqlite_schema.py`
- `src/vibe3/models/flow.py`
- `docs/standards/vibe3-command-standard.md`
- `docs/standards/vibe3-user-guide.md`
- `docs/standards/v3/data-model-standard.md`

验收：

- 新 schema 与命令行为一致。
- 标准文档不再把远端真源字段描述为本地持久化真源。

## 并行策略与依赖

1. 先做 Stream A（独立可交付，直接改善用户感知）。
2. Stream B 与 Stream C 可并行，但 B 先于 D。
3. Stream D 最后执行（依赖 A/B/C 稳定后再收缩 schema）。

并行建议：

- PR-1: Stream A（读路径 + task show body）
- PR-2: Stream B（写路径停写）
- PR-3: Stream C（check 语义）
- PR-4: Stream D（schema + docs）

## Risks & Mitigations

### Risk 1: 离线体验退化

- 缓解：明确 offline 文案，保留本地最小字段显示，不阻断核心命令。

### Risk 2: 性能回退（远端查询增多）

- 缓解：命令级短生命周期缓存（单次命令内缓存），不落地持久化。

### Risk 3: 兼容脚本依赖旧 JSON 字段

- 缓解：过渡期输出兼容字段并标注 deprecation，分两个版本移除。

### Risk 4: 大规模改动导致回归

- 缓解：按 Stream 分 PR，逐个合并，每个 PR 都有独立验收。

## Verification Matrix

每个 Stream 至少执行：

```bash
uv run pytest tests/vibe3/services/test_task_bridge.py -q
uv run pytest tests/vibe3/commands/test_task_show.py -q
uv run pytest tests/vibe3/services/test_pr_query_usecase.py -q
uv run pytest tests/vibe3/services/test_check_service.py -q
```

全量回归前最小门禁：

```bash
uv run pytest tests/vibe3/commands/test_flow_show_auto_ensure.py -q
uv run pytest tests/vibe3/commands/test_task_management_commands.py -q
uv run pytest tests/vibe3/services/test_flow_status.py -q
```

## Rollback Plan

1. 若 Stream A 出现展示回归：保留投影层代码，回退命令接线。
2. 若 Stream B/C 引发流程中断：恢复旧写路径与 check 行为开关。
3. Schema 收缩必须最后做；一旦执行，需保留一次性 migration 回滚脚本。

## Done Criteria

1. 无命令再依赖本地回填远端真源字段。
2. `task show` 在线可稳定显示 remote title/body，离线降级明确。
3. `check --init/--fix` 不再承担真源回填职责。
4. 数据模型、命令行为、文档标准三者一致。
