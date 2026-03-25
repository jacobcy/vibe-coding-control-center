# Vibe3 Architecture Break Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在可控的破坏性改动下，完成 Vibe3 命令层-服务层-持久层的职责重构，降低耦合与重复，恢复可持续扩展空间。

**Architecture:** 采用”薄命令层 + 用例服务层 + 仓储/网关层 + UI 渲染层”的分层重构。先抽离高重复执行链路（run/review/plan/handoff），再拆大文件与兼容层，最后做破坏性兼容清理。每阶段都必须通过同一组回归门禁和指标门禁。

**Tech Stack:** Python 3.10+, Typer, pytest, ruff, mypy, loguru, SQLiteClient, uv

---

## 执行进度（2026-03-25 更新）

### ✅ Phase 0: 分支与基线冻结
- **状态**: 已完成
- **提交**: e6bf8b7 (refactor: begin architecture break - service layer cleanup)
- **基线**: Python LOC 19696/20000, 113 tests passing
- **说明**: 以当前重构分支为基准，跳过创建新分支步骤

### ✅ Phase 1: 命令层瘦身（run/handoff）
- **状态**: 已完成
- **提交**: 8ef10ae (refactor: extract handoff orchestration into usecase service)
- **成果**:
  - 创建 `RunUseCase` 服务层 (tests: 4 passing)
  - 创建 `HandoffUseCase` 服务层 (tests: 8 passing)
  - 基线测试全绿 (21 tests passing)
  - 类型检查通过

### ✅ Phase 2: 流程统一（flow/review/plan）
- **状态**: 已完成 (Task 2.1)
- **提交**: 待提交（LOC 超限）
- **成果**:
  - 创建 `ExecutionPipeline` 统一执行管线 (tests: 6 passing)
  - 定义 `ExecutionRequest` 和 `ExecutionResult` 标准类型
  - 协调 agent 执行、artifact 持久化、event 记录

### 🔄 Phase 3: 大文件拆分与职责下沉
- **状态**: 进行中
- **当前进度**:
  - ✅ 创建 `git_branch_ops.py` (113 lines)
  - 🔄 重构 `git_client.py`（待删除重复代码）
  - ⏳ 重构 `task_bridge_mixin.py`
  - ⏳ 重构 `handoff.py`
  - ⏳ 重构 `run.py`
- **当前指标**: Python LOC 20264/20000 (超出 264 行)
- **阻塞**: 需删除重复代码降低 LOC

### ⏳ Phase 4: 破坏性兼容清理
- **状态**: 未开始

### ⏳ Final Gate: 全量验证
- **状态**: 未开始

---

## 当前阻塞问题

**Python LOC 超限**:
- 当前: 20264/20000
- 超出: 264 行
- 原因: 添加了新服务层代码和 git_branch_ops，未删除重复部分

**解决方案**:
1. 完成 git_client.py 重构，删除重复的分支操作代码（~70 行）
2. 继续拆分其他大文件，消除重复逻辑
3. 利用 usecase 层简化命令层代码

---

## Scope And Guardrails

- 允许破坏性变更：CLI deprecated 入口、兼容别名、历史内部 helper 的移除。
- 不在本计划内：新增业务功能、外部 API 语义扩展、数据库 schema 大改。
- 质量硬门槛：
  - Python LOC 低于 19000。
  - 所有文件小于或等于 300 行，目标热点文件小于或等于 260 行。
  - commands 总 LOC 较当前基线再降 10%。

## Baseline Verification Set

- `vibe3 inspect metrics`
- `uv run pytest tests/vibe3/commands/test_run.py tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_plan.py tests/vibe3/commands/test_plan_helpers.py tests/vibe3/commands/test_handoff_command.py tests/vibe3/commands/test_flow_actor_defaults.py tests/vibe3/commands/test_task_management_commands.py tests/vibe3/services/test_agent_execution_service.py -q`
- `uv run pytest tests/vibe3/services/test_context_builder.py tests/vibe3/services/test_review_runner.py tests/vibe3/services/test_flow_creation.py tests/vibe3/services/test_flow_events.py tests/vibe3/services/test_flow_status.py tests/vibe3/services/test_snapshot_service.py -q`

## Phase 0: Branch And Baseline Freeze

### Task 0.1: 建立破坏性重构分支

**Files:**
- Modify: `.git` refs only

**Step 1: 创建分支**

Run: `git checkout -b refactor/vibe3-architecture-break`

**Step 2: 记录当前改动统计**

Run: `git --no-pager diff --stat > temp/refactor-baseline-diffstat.txt`

**Step 3: 记录结构指标基线**

Run: `vibe3 inspect metrics > temp/refactor-baseline-metrics.txt`

**Step 4: 运行基线测试**

Run: 使用 Baseline Verification Set
Expected: 全绿

**Step 5: Commit**

```bash
git add temp/refactor-baseline-diffstat.txt temp/refactor-baseline-metrics.txt
git commit -m "chore: capture architecture refactor baseline"
```

## Phase 1: 命令层瘦身（run/handoff）

### Task 1.1: 为 run 用例服务补失败测试

**Files:**
- Create: `tests/vibe3/services/test_run_usecase.py`
- Test: `tests/vibe3/services/test_run_usecase.py`

**Step 1: 写失败测试（仅描述 orchestration 行为）**

覆盖：参数归一、session 恢复、execute_agent 调用、artifact/event 持久化顺序。

**Step 2: 跑单测确认失败**

Run: `uv run pytest tests/vibe3/services/test_run_usecase.py -q`
Expected: FAIL（模块/符号不存在）

### Task 1.2: 实现 run 用例服务最小版本

**Files:**
- Create: `src/vibe3/services/run_usecase.py`
- Modify: `src/vibe3/commands/run.py`
- Modify: `src/vibe3/models/agent_execution.py`
- Test: `tests/vibe3/services/test_run_usecase.py`

**Step 1: 实现最小可用 RunUseCase**

只做编排，不做 UI 输出。

**Step 2: 接入命令层**

`run.py` 保留 Typer 入口与输出，核心流程下沉到 `RunUseCase`。

**Step 3: 跑目标测试**

Run: `uv run pytest tests/vibe3/services/test_run_usecase.py tests/vibe3/commands/test_run.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/vibe3/services/test_run_usecase.py src/vibe3/services/run_usecase.py src/vibe3/commands/run.py src/vibe3/models/agent_execution.py
git commit -m "refactor: extract run orchestration into usecase service"
```

### Task 1.3: 为 handoff 用例服务补失败测试

**Files:**
- Create: `tests/vibe3/services/test_handoff_usecase.py`
- Test: `tests/vibe3/services/test_handoff_usecase.py`

**Step 1: 写失败测试**

覆盖：reference 记录、artifact 写入、event 追加、错误路径。

**Step 2: 运行确认失败**

Run: `uv run pytest tests/vibe3/services/test_handoff_usecase.py -q`
Expected: FAIL

### Task 1.4: 实现 handoff 用例服务并接入命令层

**Files:**
- Create: `src/vibe3/services/handoff_usecase.py`
- Modify: `src/vibe3/commands/handoff.py`
- Modify: `src/vibe3/services/handoff_event_service.py`
- Test: `tests/vibe3/services/test_handoff_usecase.py`

**Step 1: 最小实现 HandoffUseCase**

**Step 2: 命令层替换旧逻辑**

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/services/test_handoff_usecase.py tests/vibe3/commands/test_handoff_command.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add tests/vibe3/services/test_handoff_usecase.py src/vibe3/services/handoff_usecase.py src/vibe3/commands/handoff.py src/vibe3/services/handoff_event_service.py
git commit -m "refactor: extract handoff orchestration into usecase service"
```

## Phase 2: 流程统一（flow/review/plan）

### Task 2.1: 抽象统一执行管线接口

**Files:**
- Create: `src/vibe3/services/execution_pipeline.py`
- Modify: `src/vibe3/services/agent_execution_service.py`
- Modify: `src/vibe3/services/handoff_event_service.py`
- Test: `tests/vibe3/services/test_agent_execution_service.py`

**Step 1: 写失败测试（pipeline 合同）**

新增 pipeline 合同测试（输入 request，输出标准 outcome + 事件记录结果）。

**Step 2: 实现最小接口**

将 execute + artifact + event 串起来，暴露单一入口。

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/services/test_agent_execution_service.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/services/execution_pipeline.py src/vibe3/services/agent_execution_service.py src/vibe3/services/handoff_event_service.py tests/vibe3/services/test_agent_execution_service.py
git commit -m "refactor: introduce unified execution pipeline contract"
```

### Task 2.2: review/plan 改为统一 pipeline

**Files:**
- Modify: `src/vibe3/commands/review.py`
- Modify: `src/vibe3/commands/plan_helpers.py`
- Modify: `tests/vibe3/commands/test_review_pr.py`
- Modify: `tests/vibe3/commands/test_plan_helpers.py`

**Step 1: 写失败测试（调用路径迁移）**

**Step 2: 修改实现**

`review.py` 和 `plan_helpers.py` 仅保留参数映射与 UI 组装。

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_plan_helpers.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/commands/review.py src/vibe3/commands/plan_helpers.py tests/vibe3/commands/test_review_pr.py tests/vibe3/commands/test_plan_helpers.py
git commit -m "refactor: migrate review and plan commands to unified pipeline"
```

### Task 2.3: flow 服务边界重整

**Files:**
- Modify: `src/vibe3/commands/flow.py`
- Modify: `src/vibe3/services/flow_service.py`
- Create: `src/vibe3/services/flow_usecase.py`
- Modify: `tests/vibe3/commands/test_flow_actor_defaults.py`
- Modify: `tests/vibe3/services/test_flow_events.py`

**Step 1: 写失败测试（flow lifecycle orchestration）**

**Step 2: 实现 FlowUseCase 并命令层接入**

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/commands/test_flow_actor_defaults.py tests/vibe3/services/test_flow_events.py tests/vibe3/services/test_flow_status.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/commands/flow.py src/vibe3/services/flow_service.py src/vibe3/services/flow_usecase.py tests/vibe3/commands/test_flow_actor_defaults.py tests/vibe3/services/test_flow_events.py tests/vibe3/services/test_flow_status.py
git commit -m "refactor: split flow command orchestration into usecase layer"
```

## Phase 3: 大文件拆分与职责下沉

### Task 3.1: 拆分 git_client

**Files:**
- Create: `src/vibe3/clients/git_branch_ops.py`
- Create: `src/vibe3/clients/git_worktree_ops.py`
- Create: `src/vibe3/clients/git_status_ops.py`
- Modify: `src/vibe3/clients/git_client.py`
- Test: `tests/vibe3/clients/`（按现有结构增补）

**Step 1: 写失败测试（最小 smoke）**

**Step 2: 提取实现并保留外观 API**

**Step 3: 跑客户端测试**

Run: `uv run pytest tests/vibe3/clients -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/clients/git_client.py src/vibe3/clients/git_branch_ops.py src/vibe3/clients/git_worktree_ops.py src/vibe3/clients/git_status_ops.py tests/vibe3/clients
git commit -m "refactor: split git client into focused operation modules"
```

### Task 3.2: 拆分 task_bridge_mixin

**Files:**
- Create: `src/vibe3/services/task_bridge_lookup.py`
- Create: `src/vibe3/services/task_bridge_mutation.py`
- Modify: `src/vibe3/services/task_bridge_mixin.py`
- Test: `tests/vibe3/services/` 对应桥接测试

**Step 1: 写失败测试（lookup/mutation contract）**

**Step 2: 拆分实现并保持入口兼容（阶段内）**

**Step 3: 跑测试**

Run: `uv run pytest tests/vibe3/services -k "task_bridge or task_management" -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/services/task_bridge_mixin.py src/vibe3/services/task_bridge_lookup.py src/vibe3/services/task_bridge_mutation.py tests/vibe3/services
git commit -m "refactor: split task bridge mixin by read-write responsibilities"
```

## Phase 4: 破坏性兼容清理

### Task 4.1: 移除 CLI 兼容别名与隐藏废弃入口

**Files:**
- Modify: `src/vibe3/cli.py`
- Modify: `src/vibe3/commands/run.py`
- Modify: `src/vibe3/commands/hooks.py`
- Modify: `README.md`
- Modify: `docs/DEVELOPMENT.md`

**Step 1: 写失败测试（旧入口应不存在/报错）**

**Step 2: 移除 deprecated 路径**

包括 `--file` 别名和隐藏旧 hooks 子命令。

**Step 3: 跑命令测试 + 文档检查**

Run: `uv run pytest tests/vibe3/commands -q`
Expected: PASS

**Step 4: Commit**

```bash
git add src/vibe3/cli.py src/vibe3/commands/run.py src/vibe3/commands/hooks.py README.md docs/DEVELOPMENT.md
git commit -m "refactor!: remove deprecated cli compatibility surfaces"
```

## Final Gate

### Task F.1: 全量验证

**Files:**
- No code changes unless fix required

**Step 1: 运行质量检查**

- `uv run ruff check src/vibe3`
- `uv run mypy src/vibe3`
- `uv run pytest -q`

**Step 2: 运行结构指标检查**

- `vibe3 inspect metrics`

**Step 3: 对比基线**

- `git --no-pager diff --stat`
- 对比 `temp/refactor-baseline-metrics.txt`

**Step 4: 输出结果摘要**

写入 `docs/reports/2026-03-25-vibe3-architecture-break-summary.md`

**Step 5: Commit**

```bash
git add docs/reports/2026-03-25-vibe3-architecture-break-summary.md
git commit -m "docs: add architecture break refactor verification summary"
```

## Rollback Strategy

- 每个 Phase 独立提交，必要时 `git revert <commit>` 按阶段回滚。
- 禁止 squash 全过程，确保可回滚粒度。
- 一旦 Final Gate 不达标，禁止进入发布或合并流程。

## Deliverables

- 用例服务层：`run_usecase`, `handoff_usecase`, `flow_usecase`
- 统一执行管线：`execution_pipeline`
- 拆分后基础模块：`git_*_ops`, `task_bridge_*`
- 重构验证报告：`docs/reports/2026-03-25-vibe3-architecture-break-summary.md`
