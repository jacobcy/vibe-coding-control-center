# Vibe3 Structural Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在当前代码基础上完成一次面向长期维护的结构化重构，目标是极薄命令层、保留承担编排职责的 usecase 服务层、收敛基础设施适配层复杂度，并把 Python 规模重新压回可维护范围。

**Architecture:** 采用“极薄 CLI 命令层 + usecase/application service 层 + 薄 infrastructure adapter 层 + UI 渲染层”的结构。命令层只负责参数解析、输入校验、调用用例和输出；usecase service 负责跨依赖编排；client/ops/mixin 等基础设施模块只保留单一能力封装。优先收敛 plan/run/review 的重复执行链路，再拆分 handoff、flow、git client、task bridge 等热点文件，最后清理兼容层并通过统一门禁验证。

**Tech Stack:** Python 3.10+, Typer, pytest, ruff, mypy, loguru, SQLiteClient, uv

---

## Plan Status

本计划自 2026-03-26 起生效，作为当前分支的执行版本。

## Current Baseline

- Python LOC: 19573 / 20000
- 超限文件:
  - `src/vibe3/commands/handoff.py` (507)
  - `src/vibe3/clients/git_client.py` (357)
  - `src/vibe3/services/task_bridge_mixin.py` (352)
  - `src/vibe3/commands/run.py` (313)
- 已有可复用重构基础:
  - `src/vibe3/clients/git_branch_ops.py`
  - `src/vibe3/commands/flow_lifecycle.py`
  - `src/vibe3/commands/flow_status.py`
  - `src/vibe3/services/agent_execution_service.py`
  - `src/vibe3/services/handoff_recorder_unified.py`

## Success Criteria

- Python LOC <= 19000
- 所有 Python 文件 <= 300 行
- 热点命令文件目标 <= 260 行：`run.py`、`handoff.py`、`flow.py`
- commands 只保留 CLI 边界职责：参数解析、轻量校验、调用 usecase、渲染输出、退出码
- 允许 usecase service 保留中等厚度的编排逻辑，但禁止继续把编排散落回 commands
- infrastructure service / adapter 保持薄且单职责，不再混合 orchestration、存储和 UI 逻辑
- commands 不再直接调用 `execute_agent`、`record_handoff_unified`、`SQLiteClient` 等底层编排或持久化细节
- plan/run/review 共用单一执行编排入口，不再各自拼接一套 execute + handoff 保存流程
- `git_client.py` 仅保留 facade 和公共 helper，不再承载 worktree/status/stash 全部实现
- task bridge 读写职责拆开，不再集中在单个 mixin 文件中
- 移除明确废弃的 CLI 兼容入口
- 完成 ruff、mypy、pytest 和 metrics 门禁，并生成总结报告

## Layering Rules

- `commands/`：只处理 CLI 边界，不承载业务编排
- `services/*_usecase.py` 或等价应用服务：负责跨多个依赖的顺序控制与业务编排
- `services/*_builder.py`、`services/*_recorder.py`、`services/*_event_service.py`：只保留单一能力，不承担完整用例
- `clients/*_ops.py`：只封装外部系统或 Git 操作细节，不向上泄露 CLI/UI 语义
- `ui/`：只负责展示，不包含状态变更或副作用

## Non-Goals

- 不新增业务功能
- 不扩展外部 API 语义
- 不调整 SQLite schema
- 不为单一场景新增新的命令族

## Verification Set

- `vibe3 inspect metrics`
- `uv run pytest tests/vibe3/commands/test_run.py tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_plan.py tests/vibe3/commands/test_plan_helpers.py tests/vibe3/commands/test_handoff_command.py tests/vibe3/commands/test_flow_actor_defaults.py tests/vibe3/commands/test_task_management_commands.py -q`
- `uv run pytest tests/vibe3/services/test_agent_execution_service.py tests/vibe3/services/test_context_builder.py tests/vibe3/services/test_plan_run_context_builder.py tests/vibe3/services/test_flow_creation.py tests/vibe3/services/test_flow_events.py tests/vibe3/services/test_flow_status.py tests/vibe3/services/test_handoff_recorder_unified.py tests/vibe3/services/test_task_bridge.py tests/vibe3/services/test_task_management.py -q`

---

## Phase 0: Refresh Baseline And Guardrails

### Task 0.1: 刷新基线记录

**Files:**
- Create: `temp/2026-03-26-refactor-metrics.txt`
- Create: `temp/2026-03-26-refactor-diffstat.txt`

**Step 1: 记录当前结构指标**

Run: `vibe3 inspect metrics > temp/2026-03-26-refactor-metrics.txt`
Expected: 输出当前 Shell / Scripts / Python 指标

**Step 2: 记录当前 diff 统计**

Run: `git --no-pager diff --stat > temp/2026-03-26-refactor-diffstat.txt`
Expected: 生成当前分支差异摘要

**Step 3: 跑当前回归集**

Run: 使用 Verification Set
Expected: 记录当前通过/失败状态

**Step 4: Commit**

```bash
git add temp/2026-03-26-refactor-metrics.txt temp/2026-03-26-refactor-diffstat.txt
git commit -m "chore: refresh structural refactor baseline"
```

## Phase 1: Introduce Shared Usecase Orchestration For Plan / Run / Review

### Task 1.1: 为共享用例编排补合同测试

**Files:**
- Create: `tests/vibe3/services/test_execution_pipeline.py`
- Modify: `tests/vibe3/commands/test_run.py`
- Modify: `tests/vibe3/commands/test_review_pr.py`
- Modify: `tests/vibe3/commands/test_plan_helpers.py`

**Step 1: 写失败测试**

覆盖：
- session id 读取
- context builder 输出传入 agent 执行器
- handoff artifact 统一保存
- dry-run 短路
- command 层只做参数映射和后置 UI/label 动作

**Step 2: 跑目标测试确认失败**

Run: `uv run pytest tests/vibe3/services/test_execution_pipeline.py tests/vibe3/commands/test_run.py tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_plan_helpers.py -q`
Expected: FAIL（缺少共享 usecase 编排入口或行为不符）

### Task 1.2: 提取共享执行用例服务

**Files:**
- Create: `src/vibe3/services/execution_pipeline.py`
- Modify: `src/vibe3/services/agent_execution_service.py`
- Modify: `src/vibe3/commands/run.py`
- Modify: `src/vibe3/commands/review.py`
- Modify: `src/vibe3/commands/plan_helpers.py`

**Step 1: 实现共享执行用例模型**

在 `execution_pipeline.py` 中实现一个 usecase-style 编排服务，负责：
- 读取 session id
- 调用上下文构建结果
- 执行 agent
- 统一写入 handoff artifact
- 返回 command 层所需结果

**Step 2: 收敛命令层**

让 `run.py`、`review.py`、`plan_helpers.py` 只保留：
- CLI 参数解析
- request 映射
- 命令特有的 UI 输出
- issue label transition

并移除 command 对 `execute_agent`、`record_handoff_unified` 等底层编排细节的直接依赖。

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/services/test_execution_pipeline.py tests/vibe3/commands/test_run.py tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_plan_helpers.py tests/vibe3/commands/test_plan.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/services/execution_pipeline.py src/vibe3/services/agent_execution_service.py src/vibe3/commands/run.py src/vibe3/commands/review.py src/vibe3/commands/plan_helpers.py tests/vibe3/services/test_execution_pipeline.py tests/vibe3/commands/test_run.py tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_review_base.py tests/vibe3/commands/test_plan_helpers.py tests/vibe3/commands/test_plan.py
git commit -m "refactor: unify plan run review execution flow"
```

## Phase 2: Thin Commands And Move Write-Side Orchestration Into Usecases

### Task 2.1: 拆分 handoff 命令并引入 handoff 写侧用例

**Files:**
- Create: `src/vibe3/commands/handoff_read.py`
- Create: `src/vibe3/commands/handoff_write.py`
- Create: `src/vibe3/services/handoff_usecase.py`
- Modify: `src/vibe3/commands/handoff.py`
- Modify: `src/vibe3/services/handoff_service.py`
- Modify: `src/vibe3/services/handoff_event_service.py`
- Modify: `tests/vibe3/commands/test_handoff_command.py`
- Modify: `tests/vibe3/services/test_handoff_file_ops.py`
- Modify: `tests/vibe3/services/test_handoff_recording.py`

**Step 1: 写失败测试**

覆盖：
- list/show 只读路径
- init/append/plan/report 等写路径
- handoff.py 只做 Typer 注册和共享入口
- handoff 写侧命令通过 usecase 完成状态变更与记录

**Step 2: 提取实现**

目标：
- `handoff_read.py` 负责 show/list 相关命令
- `handoff_write.py` 负责 init/append/record 相关命令
- `handoff_usecase.py` 负责写侧编排顺序
- `handoff.py` 降为薄入口文件
- `handoff_service.py`、`handoff_event_service.py` 退回单能力组件

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/commands/test_handoff_command.py tests/vibe3/services/test_handoff_file_ops.py tests/vibe3/services/test_handoff_recording.py tests/vibe3/services/test_handoff_recorder_unified.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/commands/handoff.py src/vibe3/commands/handoff_read.py src/vibe3/commands/handoff_write.py src/vibe3/services/handoff_usecase.py src/vibe3/services/handoff_service.py src/vibe3/services/handoff_event_service.py tests/vibe3/commands/test_handoff_command.py tests/vibe3/services/test_handoff_file_ops.py tests/vibe3/services/test_handoff_recording.py tests/vibe3/services/test_handoff_recorder_unified.py
git commit -m "refactor: split handoff command into read and write modules"
```

### Task 2.2: 完成 flow 命令层收敛并固定 usecase 边界

**Files:**
- Create: `src/vibe3/services/flow_usecase.py`
- Modify: `src/vibe3/commands/flow.py`
- Modify: `src/vibe3/commands/flow_lifecycle.py`
- Modify: `src/vibe3/commands/flow_status.py`
- Modify: `src/vibe3/services/flow_service.py`
- Modify: `tests/vibe3/commands/test_flow_actor_defaults.py`
- Modify: `tests/vibe3/services/test_flow_creation.py`
- Modify: `tests/vibe3/services/test_flow_binding.py`
- Modify: `tests/vibe3/services/test_flow_events.py`
- Modify: `tests/vibe3/services/test_flow_status.py`

**Step 1: 写失败测试**

覆盖：
- flow new / bind 的 orchestration 不再直接写 SQLite
- 生命周期命令继续委托给 service/usecase
- flow.py 不再承载 bind/new 的业务细节
- command 层不再直接调用低层 store/client 执行流程状态写入

**Step 2: 下沉 orchestration**

`flow_usecase.py` 负责：
- create flow
- bind task/spec
- auto-init handoff
- project link side effect

`flow_service.py` 保持为流程领域能力和查询接口，不再继续吸收 CLI 层的编排细节。

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/commands/test_flow_actor_defaults.py tests/vibe3/services/test_flow_creation.py tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_flow_events.py tests/vibe3/services/test_flow_status.py tests/vibe3/services/test_flow_auto_ensure.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/services/flow_usecase.py src/vibe3/commands/flow.py src/vibe3/commands/flow_lifecycle.py src/vibe3/commands/flow_status.py src/vibe3/services/flow_service.py tests/vibe3/commands/test_flow_actor_defaults.py tests/vibe3/services/test_flow_creation.py tests/vibe3/services/test_flow_binding.py tests/vibe3/services/test_flow_events.py tests/vibe3/services/test_flow_status.py tests/vibe3/services/test_flow_auto_ensure.py
git commit -m "refactor: move flow orchestration into usecase layer"
```

## Phase 3: Finish Infrastructure Splits

### Task 3.1: 完成 git client 拆分

**Files:**
- Create: `src/vibe3/clients/git_worktree_ops.py`
- Create: `src/vibe3/clients/git_status_ops.py`
- Modify: `src/vibe3/clients/git_client.py`
- Modify: `tests/vibe3/commands/test_inspect_base.py`
- Modify: `tests/vibe3/commands/test_inspect_commit.py`
- Modify: `tests/vibe3/commands/test_inspect_pr.py`

**Step 1: 写失败测试 / smoke 校验**

覆盖：
- branch facade 保持不变
- worktree/status/stash 相关行为不回归
- 调用方无需修改外观 API

**Step 2: 提取实现**

目标：
- `git_branch_ops.py` 负责 branch 操作
- `git_worktree_ops.py` 负责 worktree / common-dir / branch switch 相关实现
- `git_status_ops.py` 负责 diff/status/stash/changed-files 相关实现
- `git_client.py` 保留 facade 和共享 `_run()`

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/commands/test_inspect_base.py tests/vibe3/commands/test_inspect_commit.py tests/vibe3/commands/test_inspect_pr.py tests/vibe3/commands/test_inspect_files.py tests/vibe3/commands/test_inspect_metrics.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/clients/git_client.py src/vibe3/clients/git_worktree_ops.py src/vibe3/clients/git_status_ops.py tests/vibe3/commands/test_inspect_base.py tests/vibe3/commands/test_inspect_commit.py tests/vibe3/commands/test_inspect_pr.py tests/vibe3/commands/test_inspect_files.py tests/vibe3/commands/test_inspect_metrics.py
git commit -m "refactor: split git client by operation domain"
```

### Task 3.2: 拆分 task bridge 读写职责

**Files:**
- Create: `src/vibe3/services/task_bridge_lookup.py`
- Create: `src/vibe3/services/task_bridge_mutation.py`
- Modify: `src/vibe3/services/task_bridge_mixin.py`
- Modify: `src/vibe3/services/task_service.py`
- Modify: `tests/vibe3/services/test_task_bridge.py`
- Modify: `tests/vibe3/services/test_task_management.py`
- Modify: `tests/vibe3/services/test_task_linking.py`

**Step 1: 写失败测试**

覆盖：
- hydrate/query 走 lookup
- link/update/status 走 mutation
- task service 外部 API 保持兼容

**Step 2: 拆分实现**

目标：
- `task_bridge_lookup.py` 承担 hydrate / remote read
- `task_bridge_mutation.py` 承担 link / status update / auto link
- `task_bridge_mixin.py` 只保留轻量组合或兼容壳，必要时可删除

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/services/test_task_bridge.py tests/vibe3/services/test_task_management.py tests/vibe3/services/test_task_linking.py tests/vibe3/commands/test_task_management_commands.py tests/vibe3/commands/test_task_show.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/services/task_bridge_lookup.py src/vibe3/services/task_bridge_mutation.py src/vibe3/services/task_bridge_mixin.py src/vibe3/services/task_service.py tests/vibe3/services/test_task_bridge.py tests/vibe3/services/test_task_management.py tests/vibe3/services/test_task_linking.py tests/vibe3/commands/test_task_management_commands.py tests/vibe3/commands/test_task_show.py
git commit -m "refactor: split task bridge read and write paths"
```

## Phase 4: Remove Deprecated CLI Compatibility Surface

### Task 4.1: 删除废弃别名与隐藏旧入口

**Files:**
- Modify: `src/vibe3/cli.py`
- Modify: `src/vibe3/commands/run.py`
- Modify: `src/vibe3/commands/hooks.py`
- Modify: `README.md`
- Modify: `docs/DEVELOPMENT.md`
- Modify: `tests/vibe3/commands/test_run.py`
- Modify: `tests/vibe3/commands/test_hooks_cli.py`

**Step 1: 写失败测试**

覆盖：
- `run --file` 不再可用
- hidden hooks alias 不再注册
- 文档示例只保留正式入口

**Step 2: 清理兼容层**

移除：
- `--file` alias
- 顶层重复包装中无必要的兼容参数
- `hooks install/install-hooks/uninstall-hooks` 等隐藏废弃命令

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/commands/test_run.py tests/vibe3/commands/test_hooks_cli.py tests/vibe3/commands/test_plan.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/cli.py src/vibe3/commands/run.py src/vibe3/commands/hooks.py README.md docs/DEVELOPMENT.md tests/vibe3/commands/test_run.py tests/vibe3/commands/test_hooks_cli.py tests/vibe3/commands/test_plan.py
git commit -m "refactor!: remove deprecated cli compatibility surface"
```

## Final Gate

### Task F.1: Full Verification And Report

**Files:**
- Create: `docs/reports/2026-03-26-vibe3-structural-refactor-summary.md`

**Step 1: 运行质量检查**

Run:
- `uv run ruff check src/vibe3`
- `uv run mypy src/vibe3`
- `uv run pytest -q`

Expected: 全绿

**Step 2: 运行结构指标检查**

Run: `vibe3 inspect metrics`
Expected:
- Python LOC <= 19000
- 所有 Python 文件 <= 300

**Step 3: 对比基线**

Run:
- `git --no-pager diff --stat`
- 对比 `temp/2026-03-26-refactor-metrics.txt`

Expected: 热点文件和总 LOC 明显下降

**Step 4: 写验证总结**

在 `docs/reports/2026-03-26-vibe3-structural-refactor-summary.md` 中记录：
- 最终 metrics
- 删除/新增的结构层次
- 主要风险与后续清理项

**Step 5: Commit**

```bash
git add docs/reports/2026-03-26-vibe3-structural-refactor-summary.md
git commit -m "docs: add structural refactor verification summary"
```

## Rollback Strategy

- 每个 Phase 单独提交，禁止把整个重构 squash 成单个提交
- 如果某次拆分导致 metrics 反弹或测试面失控，按 Phase revert
- 在 Final Gate 通过前，不进入发布或合并流程

## Deliverables

- 共享执行用例服务：`execution_pipeline.py`
- handoff 写侧用例服务：`handoff_usecase.py`
- 下沉后的 flow orchestration：`flow_usecase.py`
- 拆分后的 handoff 命令层：`handoff_read.py`、`handoff_write.py`
- 拆分后的基础设施模块：`git_worktree_ops.py`、`git_status_ops.py`
- 拆分后的 task bridge 模块：`task_bridge_lookup.py`、`task_bridge_mutation.py`
- 重构验证报告：`docs/reports/2026-03-26-vibe3-structural-refactor-summary.md`