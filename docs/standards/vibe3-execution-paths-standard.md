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

核心论点：**区分执行路径的正确方式是"容器外 vs 容器内"，而不是"sync vs async"。** "sync/async"描述的是调度方式，而 no-op gate 的覆盖取决于执行是否在 orchestra 进程内完成。

## 1. 术语定义

### 1.1 容器外路径（Orchestra 进程内）

**定义**：agent 在 orchestra 进程内同步执行，orchestra 等待执行完成。

**代码路径**：
```
orchestra dispatch
  -> issue_role_sync_runner.run_issue_role_mode(async_mode=False)
    -> coordinator.dispatch_execution(mode="sync")
      -> codeagent_runner.execute_sync()
        -> CodeagentBackend.run()  (阻塞等待)
        -> _apply_unified_noop_gate()  (no-op gate)
```

**特征**：
- orchestra 进程等待 agent 完成
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
    -> pre_gate_callback (e.g., reviewer 写入 audit_ref)
    -> _apply_unified_noop_gate()  (no-op gate)
```

**特征**：
- orchestra 进程不等待 agent 完成
- no-op gate 在 tmux 子进程内的 `execute_sync()` 中触发
- gate 逻辑与容器外路径完全一致

### 1.3 为什么不用 "sync/async" 区分

"sync" 和 "async" 描述的是调度策略，不是 no-op gate 覆盖范围：

| 维度 | 容器外路径 | 容器内路径 |
|------|-----------|-----------|
| 调度方式 | sync（阻塞等待） | async（tmux 子进程） |
| 执行位置 | orchestra 进程内 | tmux 子进程内 |
| no-op gate | 覆盖 | 覆盖（统一） |
| pre_gate_callback | 支持 | 支持 |

两条路径现在共享同一个 gate 代码路径（`codeagent_runner.execute_sync()` 中的 `_apply_unified_noop_gate`），不再存在覆盖差异。

## 2. 代码位置

### 2.1 分支点

`issue_role_sync_runner.py:run_issue_role_mode()` 根据 `async_mode` 参数分流：

- `async_mode=True`：进入容器内路径
- `async_mode=False`：进入容器外路径

### 2.2 统一的 no-op gate

| 文件 | 函数 | 作用 |
|------|------|------|
| `codeagent_runner.py` `_apply_unified_noop_gate` | L55-116 | 三分支 gate 逻辑 |
| `codeagent_runner.py` `execute_sync` | L155-158 | 捕获 before_state_label |
| `codeagent_runner.py` `execute_sync` | L266-294 | 调用 pre_gate_callback + gate |

### 2.3 pre_gate_callback 机制

某些角色（如 reviewer）需要在 gate 检查前将 ref 写入 flow_state。`CodeagentCommand.pre_gate_callback` 在 gate 触发前执行，允许角色从 stdout 解析并写入 ref。

| 角色 | pre_gate_callback | 写入的 ref |
|------|-------------------|-----------|
| planner | None | plan_ref（agent 自己写入） |
| executor | None | report_ref（agent 自己写入） |
| reviewer | `_process_review_sync_result` | audit_ref（从 stdout 解析） |

## 3. No-op Gate 三分支逻辑

Gate 在 `codeagent_runner.execute_sync()` 的完成路径中执行，不分 sync/async：

1. **Missing ref → block**：required_ref 不存在，说明 agent 未产出预期结果
2. **Ref present + state unchanged → block**：agent 产出了 ref 但未改变 issue label（no-op）
3. **Ref present + state changed → pass**：正常完成

## 4. VIBE3_ASYNC_CHILD 环境变量

当 orchestra 通过 `dispatch_execution(mode="async")` 启动 tmux 子进程时，会设置 `VIBE3_ASYNC_CHILD=1` 环境变量。

**用途**：
- `codeagent_runner.py` 通过此标记跳过 lifecycle event 的 `started`/`completed` 记录（外层 tmux wrapper 已处理）
- `coordinator.py` 通过此标记跳过 capacity check 和 session 去重（避免子进程与父进程冲突）

**注意**：no-op gate 在两种模式下均触发，不受此变量影响。

## 5. 代码注释要求

以下文件必须包含执行路径说明注释：

- `issue_role_sync_runner.py`：在 `run_issue_role_mode` 函数顶部注释两条路径的分流逻辑
- `codeagent_runner.py`：在 `execute_sync` 和 `_apply_unified_noop_gate` 注释 gate 触发位置
- `coordinator.py`：在 `dispatch_execution` 注释 async 和 sync 两种模式的处理差异
