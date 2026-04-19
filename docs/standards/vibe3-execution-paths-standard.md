---
document_type: standard
title: Vibe3 Execution Paths Standard
status: active
scope: project-wide
authority:
  - execution-path-terminology
  - no-op-gate-unified
  - async-child-contract
author: Claude Sonnet 4.6
created: 2026-04-18
last_updated: 2026-04-18
related_docs:
  - docs/standards/vibe3-noop-gate-boundary-standard.md
  - docs/standards/vibe3-orchestra-runtime-standard.md
  - docs/standards/vibe3-state-sync-standard.md
  - src/vibe3/execution/issue_role_sync_runner.py
  - src/vibe3/execution/codeagent_runner.py
---

# Vibe3 Execution Paths Standard

本文档定义 Vibe3 执行路径的准确术语和架构约束。

核心论点：**区分执行路径的正确方式是"容器外 vs 容器内"，而不是"sync vs async"。** "sync/async"描述的是调度方式；worker 的 gate、handoff 和生命周期收口在统一执行壳里，但只有 sync orchestration 路径负责 gate 判断。tmux async child 只是执行壳和最小可见性容器，不承载业务 gate。role builder 也不再通过 `build_required_ref_sync_spec`、`completion_gate`、`completion_contract` 之类的声明式字段决定 worker 完成语义。

## 1. 术语定义

### 1.1 容器外路径（Orchestra 进程内）

**定义**：agent 在 orchestra 进程内同步执行，orchestra 等待执行完成。

**代码路径**：
```
orchestra dispatch
  -> issue_role_sync_runner.run_issue_role_mode(async_mode=False)
    -> coordinator.dispatch_execution(mode="sync")
      -> CodeagentExecutionService.execute_sync_request()
        -> codeagent_runner.execute_sync()
        -> CodeagentBackend.run()  (阻塞等待)
        -> _apply_unified_noop_gate()  (no-op gate)
```

**特征**：
- orchestra 进程等待 agent 完成
- worker sync 路径先经 `ExecutionCoordinator`，再委托给统一执行壳
- no-op gate 在 `codeagent_runner.execute_sync()` 中触发

### 1.2 容器内路径（tmux 子进程）

**定义**：orchestra 将 agent 调度到 tmux session 中执行，tmux 子进程独立运行，orchestra 不等待完成。

**代码路径**：
```
orchestra dispatch
  -> issue_role_sync_runner.run_issue_role_mode(async_mode=True)
    -> coordinator.dispatch_execution(mode="async")
      -> start_async_command()  -> 启动 tmux，立即返回
    -> return

tmux 子进程内部:
  -> codeagent_runner.execute_sync()
    -> CodeagentBackend.run()
    -> 记录 handoff / latest_actor / minimal lifecycle
    -> return
```

**特征**：
- orchestra 进程不等待 agent 完成
- tmux child 只负责执行与最小可见性
- 不在 tmux child 内执行 worker gate 或 pre-gate business callback

### 1.3 为什么不用 "sync/async" 区分

"sync" 和 "async" 描述的是调度策略，不是容器职责本身：

| 维度 | 容器外路径 | 容器内路径 |
|------|-----------|-----------|
| 调度方式 | sync（阻塞等待） | async（tmux 子进程） |
| 执行位置 | orchestra 进程内 | tmux 子进程内 |
| worker gate | 支持 | 不支持 |
| pre_gate_callback | 支持 | 不支持 |
| 可见性 | 完整 lifecycle + handoff + gate | 最小 lifecycle + handoff |

两条路径共享同一个执行壳，但不共享同一个 gate 责任边界：worker gate 只在 sync orchestration 路径生效，不再存在 async child 内的 completion-policy 判断。

## 2. 代码位置

### 2.1 分支点

`issue_role_sync_runner.py:run_issue_role_mode()` 根据 `async_mode` 参数分流：

- `async_mode=True`：进入容器内路径
- `async_mode=False`：进入容器外路径

### 2.2 统一的 no-op gate

| 文件 | 函数 | 作用 |
|------|------|------|
| `codeagent_runner.py` `execute_sync_request` | sync worker request -> unified shell adapter |
| `codeagent_runner.py` `_apply_unified_noop_gate` | 单一硬逻辑 gate：state unchanged -> block |
| `codeagent_runner.py` `execute_sync` | 捕获 before_state_label、记录 handoff/lifecycle、在 sync 路径调用 pre_gate_callback + gate |

worker role 的 sync spec 现在只是最小 request 装配：

- resolve options
- resolve branch
- build async request
- build sync request
- failure handler

不再在 spec 层声明 `required_ref` / `missing_ref_handler` / `completion_gate`。

### 2.3 pre_gate_callback 机制

某些 sync worker 角色（如 reviewer）需要在 gate 检查前将可见性产物写入 flow_state。`CodeagentCommand.pre_gate_callback` 只在 sync orchestration 路径、且 gate 触发前执行，允许角色从 stdout 解析并写入 ref。

| 角色 | pre_gate_callback | 写入的 ref |
|------|-------------------|-----------|
| planner | None | plan_ref（agent 自己写入） |
| executor | None | report_ref（agent 自己写入） |
| reviewer | `_process_review_sync_result` | audit_ref（从 stdout 解析） |

## 3. No-op Gate 单一硬逻辑

Gate 只在 sync orchestration 路径的 `codeagent_runner.execute_sync()` 完成路径中执行：

1. **State unchanged → block**：agent 没有离开当前 state_label
2. **State changed → pass**：agent 自己完成了状态推进

ref 现在只是可见性证据，不是单独的 gate 分支。

## 4. VIBE3_ASYNC_CHILD 环境变量

当 orchestra 通过 `dispatch_execution(mode="async")` 启动 tmux 子进程时，会设置 `VIBE3_ASYNC_CHILD=1` 环境变量。

**用途**：
- `codeagent_runner.py` 通过此标记跳过 lifecycle event 的 `started`/`completed` 记录（外层 tmux wrapper 已处理）
- `codeagent_runner.py` 通过此标记跳过 worker `pre_gate_callback` 与 no-op gate（异步子进程不承载业务后处理）
- `coordinator.py` 通过此标记跳过 capacity check 和 session 去重（避免子进程与父进程冲突）

**注意**：设置此变量后，tmux async child 只保留执行与最小可见性，不再触发 worker gate。

## 5. 代码注释要求

以下文件必须包含执行路径说明注释：

- `issue_role_sync_runner.py`：在 `run_issue_role_mode` 函数顶部注释两条路径的分流逻辑
- `codeagent_runner.py`：在 `execute_sync` 和 `_apply_unified_noop_gate` 注释 gate 触发位置
- `coordinator.py`：在 `dispatch_execution` 注释 async、worker sync、non-worker sync 三种处理差异
