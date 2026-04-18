---
document_type: standard
title: Vibe3 Execution Paths Standard
status: active
scope: project-wide
authority:
  - execution-path-terminology
  - no-op-gate-coverage
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

**定义**：agent 在 orchestra 进程内同步执行，orchestra 等待执行完成后再运行 post_sync_hook。

**代码路径**：
```
orchestra dispatch
  -> issue_role_sync_runner.run_issue_role_mode(async_mode=False)
    -> before_snapshot
    -> coordinator.dispatch_execution(mode="sync")
      -> CodeagentBackend.run()  (阻塞等待)
    -> after_snapshot
    -> post_sync_hook  (包含 no-op gate)
```

**特征**：
- orchestra 进程拥有完整的 before/after snapshot
- no-op gate 在 `apply_required_ref_post_sync` 中执行
- 执行完成后，issue 状态要么被 agent 正确推进，要么被 block

### 1.2 容器内路径（tmux 子进程）

**定义**：orchestra 将 agent 调度到 tmux session 中执行，tmux 子进程独立运行，orchestra 不等待完成。

**代码路径**：
```
orchestra dispatch
  -> issue_role_sync_runner.run_issue_role_mode(async_mode=True)
    -> coordinator.dispatch_execution(mode="async")
      -> start_async_command()  -> 启动 tmux，立即返回
    -> return  (没有 snapshot，没有 post_sync_hook)

tmux 子进程内部:
  -> codeagent_runner.execute_sync()
    -> CodeagentBackend.run()
    -> 记录 lifecycle event / state_transitioned event
    -> 没有 post_sync_hook / 没有 no-op gate
```

**特征**：
- orchestra 进程不等待 agent 完成
- 没有 before/after snapshot
- **no-op gate 不触发**：这是当前架构的已知缺陷（见 section 3）
- agent 完成后状态推进完全依赖 agent 自身的 prompt 执行

### 1.3 为什么不用 "sync/async" 区分

"sync" 和 "async" 描述的是调度策略，不是 no-op gate 覆盖范围：

| 维度 | 容器外路径 | 容器内路径 |
|------|-----------|-----------|
| 调度方式 | sync（阻塞等待） | async（tmux 子进程） |
| 执行位置 | orchestra 进程内 | tmux 子进程内 |
| no-op gate | 覆盖 | 未覆盖 |
| snapshot | 有 before/after | 无 |
| post_sync_hook | 执行 | 不执行 |

"sync 路径有 no-op gate" 是对的，但原因不是"同步"，而是"在 orchestra 进程内完成"。如果将来改成异步回调但仍在 orchestra 进程内处理结果，no-op gate 同样可以覆盖。

反过来，"async 路径没有 no-op gate" 是因为 tmux 子进程独立运行，而不是因为"异步"本身。

## 2. 当前两条路径的代码位置

### 2.1 分支点

`issue_role_sync_runner.py:run_issue_role_mode()` 根据 `async_mode` 参数分流：

- `async_mode=True`（L80-125）：进入容器内路径
- `async_mode=False`（L127-192）：进入容器外路径

### 2.2 容器外关键代码

| 文件 | 函数 | 作用 |
|------|------|------|
| `issue_role_sync_runner.py` L127-134 | before_snapshot | 拍摄执行前状态 |
| `issue_role_sync_runner.py` L136-145 | coordinator.dispatch_execution | 同步执行 agent |
| `issue_role_sync_runner.py` L175-192 | post_sync_hook | 执行 no-op gate |

### 2.3 容器内关键代码

| 文件 | 函数 | 作用 |
|------|------|------|
| `issue_role_sync_runner.py` L80-108 | async dispatch | 启动 tmux，立即返回 |
| `codeagent_runner.py` L53-208 | execute_sync | tmux 子进程内的同步执行 |
| `codeagent_runner.py` L139-182 | lifecycle event 记录 | 记录 completed/state_transitioned |

## 3. 已知缺陷：容器内路径的 no-op gap

### 3.1 问题描述

当 agent 在容器内（tmux）执行时，no-op gate 不触发。这意味着：

1. agent 完成工作后如果没改 label，系统不会 block
2. orchestra 下一轮 dispatch 看到同一 label，重复派发
3. 形成无限 dispatch 循环

**实际案例**：issue #323 executor 反复被 dispatch，因为 tmux 内的 agent 完成后没有将 label 从 `state/in-progress` 推走，而 no-op gate 不在容器内路径中。

### 3.2 根因

`codeagent_runner.py` 的 `execute_sync` 只记录 lifecycle event 和 `state_transitioned` event，不执行 `post_sync_hook`（即 `apply_required_ref_post_sync`）。

这不是疏忽，而是架构限制：no-op gate 需要 before/after snapshot 上下文，而容器内路径没有 snapshot 机制。

### 3.3 影响范围

所有通过 `async_mode=True` 调度的角色执行都可能受影响：

- executor（通过 `dispatch_run_command_async`）
- planner（如果配置为 async 模式）
- reviewer（如果配置为 async 模式）

### 3.4 当前缓解措施

1. agent prompt 约定要求 agent 自己修改 issue label
2. dispatch predicate 的 `not live` 检查防止 tmux session 运行中重复派发
3. `codeagent_runner.py` 中记录 `state_transitioned` event 供事后诊断

### 3.5 长期修复方向

| 方案 | 描述 | 复杂度 |
|------|------|--------|
| A. tmux 完成回调 | tmux session 结束后触发 orchestra 回调执行 no-op gate | 高 |
| B. 容器内 no-op gate | 在 codeagent_runner 中实现简化版 no-op gate（不需要 snapshot） | 中 |
| C. 状态轮询 | orchestra 定期检查 tmux session 是否完成，完成后执行 no-op gate | 中 |

方案 B 是当前最小修复方向：在 `codeagent_runner.py` 的完成路径中，检查 agent 是否产出了 required ref 并修改了 label，如果两者都没发生则 block issue。

## 4. VIBE3_ASYNC_CHILD 环境变量

当 orchestra 通过 `dispatch_execution(mode="async")` 启动 tmux 子进程时，会设置 `VIBE3_ASYNC_CHILD=1` 环境变量（见 `run.py:dispatch_run_command_async` L287）。

**用途**：
- `codeagent_runner.py` 通过此标记跳过 lifecycle event 的 `started`/`completed` 记录（外层 tmux wrapper 已处理）
- `coordinator.py` 通过此标记跳过 capacity check 和 session 去重（避免子进程与父进程冲突）

**注意**：此变量只标记"我是在 tmux 子进程内运行"，不改变 no-op gate 的执行逻辑。

## 5. 代码注释要求

以下文件必须包含执行路径说明注释：

- `issue_role_sync_runner.py`：在 `run_issue_role_mode` 函数顶部注释两条路径的分流逻辑
- `codeagent_runner.py`：在 `execute_sync` 完成路径注释 no-op gate 缺失的已知限制
- `coordinator.py`：在 `dispatch_execution` 注释 async 和 sync 两种模式的处理差异
