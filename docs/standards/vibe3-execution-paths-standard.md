---
document_type: standard
title: Vibe3 Execution Paths Standard
status: active
scope: project-wide
authority:
  - execution-path-terminology
  - sync-chain-contract
  - orchestration-dispatch-only
author: Claude Sonnet 4.6
created: 2026-04-18
last_updated: 2026-04-19
related_docs:
  - docs/standards/vibe3-noop-gate-boundary-standard.md
  - docs/standards/vibe3-orchestra-runtime-standard.md
  - docs/standards/vibe3-state-sync-standard.md
  - src/vibe3/execution/issue_role_sync_runner.py
  - src/vibe3/execution/codeagent_runner.py
---

# Vibe3 Execution Paths Standard

本文档定义 Vibe3 执行路径的准确术语和架构约束。

## 核心架构原则

**容器（async tmux wrapper）只是防阻塞薄壳，同步链（sync chain）在容器内执行。**

当前架构已遵循的原则：
1. **Orchestration 只派发**：coordinator/domain handlers 只负责 session/capacity check + dispatch，不接管 state，不做业务判断
2. **Async wrapper 只防阻塞**：tmux 容器不承载业务逻辑，只包裹同步链
3. **Sync chain 内做业务**：gate/callback/handoff/lifecycle 都在 `execute_sync`（同步链）内执行，无论是 orchestration sync 还是 async child
4. **tmux 观测只是 checkpoint**：async wrapper 可以记录容器已启动，但这不是业务 lifecycle，也不推进 state

## 1. 术语定义

### 1.1 同步链（Sync Chain）

**定义**：`codeagent_runner.execute_sync()` 是真正的业务执行单元，包含完整的 gate/callback/handoff/lifecycle。

**职责**：
- 执行 agent（CodeagentBackend.run）
- 记录 handoff
- 记录 lifecycle events（started/completed）
- 执行 pre_gate_callback（如 reviewer 解析 stdout → audit_ref）
- 执行 no-op gate（state unchanged → block）

**位置**：无论从哪里调用，同步链都在 `execute_sync` 内，不在 orchestration 层。

---

### 1.2 容器外路径（Orchestration sync）

**定义**：orchestration 进程直接调用同步链，阻塞等待完成。

**代码路径**：
```
orchestra dispatch
  -> domain/handlers/dispatch.py  (只派发，不改 state)
    -> coordinator.dispatch_execution(mode="sync")  (只 capacity check)
      -> CodeagentExecutionService.execute_sync_request()
        -> execute_sync()  ← 同步链开始
          -> agent run
          -> handoff
          -> pre_gate_callback
          -> no-op gate  ← 同步链结束
    -> return result
```

**特征**：
- orchestration 等待同步链完成
- 同步链在 orchestration 进程内，但 orchestration 不接管 state
- gate 改 state → orchestration 观察 state → 下一步派发

---

### 1.3 容器内路径（Async tmux wrapper）

**定义**：orchestration 启动 tmux 容器，容器内调用同步链，orchestration 不等待。

**代码路径**：
```
orchestra dispatch
  -> domain/handlers/dispatch.py  (只派发)
    -> coordinator.dispatch_execution(mode="async")  (只 capacity check)
      -> start_async_command()  → 启动 tmux wrapper
      -> add_event("tmux_*_started")  → 容器 checkpoint
    -> return handle (立即返回)

tmux wrapper 内部:
  -> execute_sync()  ← 同步链开始（与容器外路径完全相同）
    -> agent run
    -> handoff
    -> pre_gate_callback
    -> no-op gate  ← 同步链结束
  -> exit
```

**特征**：
- orchestration 不等待同步链完成
- 同步链在 tmux 子进程内，orchestration 不接管 state
- tmux checkpoint 只表示容器已起，不代表业务执行生命周期
- gate 改 state → orchestration 观察 state → 下一步派发

---

### 1.4 Orchestration 职责边界

**只派发，不接管 state**：

| 层级 | 职责 | 是否改 state |
|------|------|-------------|
| domain/handlers | 读取 flow_state，调用 coordinator | ❌ 只读取上下文 |
| coordinator | session/capacity check，launch execution | ❌ 只防重复/阻塞 |
| execute_sync | gate/callback/handoff/lifecycle | ✅ gate 改 state（block） |

**关键约束**：
- orchestration 只观察 state_label，不主动修改
- state 推进由 agent（通过 label 操作）或 gate（block）完成
- orchestration 通过 dispatch predicate 判断下一步

---

## 2. Gate/Callback 的正确位置

### 2.1 Gate 在同步链内

**位置**：`execute_sync()` 第280行

```python
# execute_sync (同步链)
if command.issue_number is not None:
    _apply_unified_noop_gate(...)
    # gate 内部：
    # - state unchanged → block_issue() → state_label = "state/blocked"
    # - state changed → pass
```

**执行路径**：
- orchestration sync → execute_sync → gate
- async child → execute_sync → gate

**两者完全相同，gate 都在同步链内。**

---

### 2.2 pre_gate_callback 在同步链内

**位置**：`execute_sync()` 第272行

```python
# execute_sync (同步链)
if command.pre_gate_callback:
    command.pre_gate_callback(stdout=agent_result.stdout)
    # reviewer callback → parse stdout → write audit_ref → handoff
```

**执行路径**：
- orchestration sync → execute_sync → callback
- async child → execute_sync → callback

**两者完全相同，callback 都在同步链内。**

---

## 3. 当前实现的职责落点

### 3.1 domain/handlers 只派发

```python
# executor handler (dispatch.py)
audit_ref = flow_state.get("audit_ref")  # 只读取，不改
_dispatch_role_intent(role="executor", ...)  # 只派发
# NO gate, NO callback, NO state modification
```

### 3.2 coordinator 只防阻塞

```python
# coordinator.dispatch_execution
live_sessions = registry.get_truly_live_sessions(...)  # 防重复
capacity.can_dispatch(...)  # 容量检查
start_async_command(...)  # 启动
store.add_event("tmux_*_started")  # checkpoint only
# NO gate, NO callback, NO state modification
```

### 3.3 业务逻辑都在 execute_sync

```python
# execute_sync
record_handoff_unified(...)  # handoff
persist_execution_lifecycle_event(...)  # lifecycle
_process_review_sync_result(...)  # callback (reviewer)
_apply_unified_noop_gate(...)  # gate
```

**当前实现事实**：
- orchestration 层没有 gate/callback/state 推进逻辑
- `VIBE3_ASYNC_CHILD` 只服务 outer coordinator 的防重/容量判断
- tmux wrapper 只保留容器 checkpoint，不承载业务 lifecycle
- 真正的业务收口仍在 sync shell 内完成

这说明当前主链已经大幅收敛，但不等于 Issue 476 已自动关闭；476 仍然负责验证是否要进一步收紧 async wrapper 与 sync shell 的边界表达。

---

## 4. VIBE3_ASYNC_CHILD 环境变量

**用途**：
- `coordinator.py` 通过此标记跳过 capacity/session check（避免 child 与 parent 冲突）
- **不改变同步链行为**：child 内的 execute_sync 仍然执行完整的 gate/callback

**注意**：当前实现里，async child 与 orchestration sync 共享完全相同的 execute_sync 行为，包括 gate/callback。

---

## 5. 代码注释要求

以下文件必须包含执行路径说明注释：

- `issue_role_sync_runner.py`：在 `run_issue_role_mode` 函数顶部注释两条路径的分流逻辑
- `codeagent_runner.py`：在 `execute_sync` 注释"同步链开始"，在 gate/callback 注释"业务逻辑"
- `coordinator.py`：在 `dispatch_execution` 注释"只防阻塞，不接管 state"
- `domain/handlers/*.py`：在 handler 函数注释"只派发，不改 state"

---

## 6. Issue 476 边界

Issue 476 不是为了证明 “orchestra 必须拿回 callback 结果”。

它要验证的是：
- async wrapper 是否还需要保留任何会误导人的“独立业务边界”表述
- `VIBE3_ASYNC_CHILD` 是否被严格限制在 outer coordinator guard 范围内
- 在不破坏现有闭环的前提下，sync shell 与 async wrapper 的职责是否还能继续收紧

当前标准能确认的只有实现事实：
- orchestration 只派发
- async wrapper 只防阻塞
- sync shell 负责 gate/callback/handoff/lifecycle

是否还要进一步做结构收口，需要以独立实现和回归验证为准，而不是直接从现状文档化推导结论。
