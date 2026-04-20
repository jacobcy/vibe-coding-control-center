# Issue #481 分析结果 - vibe3 serve 闭环断点

## 问题定位

### Bug A: Manager dispatch 请求准备失败导致 issue 冻结 ✅ 已定位

**问题路径**：
```
handle_manager_dispatched() 
  → build_manager_request() 
    → FlowManager.create_flow_for_issue() 失败/返回 None
      → 只写日志，无错误处理
        → issue 冻结
```

**根本原因**：

在 `src/vibe3/domain/handlers/issue_state_dispatch.py` 第 88-92 行：

```python
if request is None:
    logger.bind(
        domain="issue_state_dispatch_handler",
        role="manager",
        issue_number=event.issue_number,
    ).error("Failed to prepare role execution request")
    return  # ❌ 直接返回，无任何错误处理
```

**问题**：
1. 没有 comment 通知用户
2. 没有 block issue
3. 没有更新 state
4. issue 永远卡在 `state/ready` 或 `state/handoff`

**`build_manager_request()` 返回 None 的场景**（`src/vibe3/roles/manager.py` 第 107-145 行）：

1. `create_flow_for_issue()` 抛出异常 → catch 后返回 None
2. `create_flow_for_issue()` 返回空 dict → `if not flow` 返回 None
3. `flow_branch` 为空 → 返回 None

**`create_flow_for_issue()` 失败场景**（`src/vibe3/execution/flow_dispatch.py`）：

1. **容量已满**（第 239-243 行）：抛出 `RuntimeError`
   ```python
   if active_count >= self.config.max_concurrent_flows:
       raise RuntimeError(f"Manager capacity reached ({active_count}/{limit})")
   ```

2. **分支创建失败**（第 247-254 行）：抛出 `RuntimeError`

3. **Flow 创建失败且并发冲突**（第 256-271 行）：抛出 `RuntimeError`

4. **PR 已 merge 但 flow 状态异常**（第 115-130 行）：调用 `block_manager_noop_issue()` 但返回 None

---

### Bug B: Review 后状态收口问题 ✅ 已分析

**代码路径**（`src/vibe3/roles/review.py`）：

1. **`_process_review_sync_result()`** (第 133-157 行)
   - 解析 review verdict
   - 创建 audit artifact
   - 调用 `HandoffService.record_audit()` 写入 audit_ref

2. **`apply_unified_noop_gate()`** (`src/vibe3/execution/noop_gate.py`)
   - 从 GitHub 读取 before_state_label 和 after_state_label
   - 如果 state 未变化 → 调用 `block_reviewer_noop_issue()`
   - 如果 state 已变化 → 记录 EVENT_STATE_TRANSITIONED

**潜在问题点**：

1. **review 完成后 state 应该变成什么？**
   - 当前代码没有显式设置 state
   - 依赖 reviewer agent 主动修改 GitHub label
   - 如果 agent 没有正确设置 state/... label，no-op gate 会 block

2. **Manager 恢复机制**
   - Review 通过后，manager 应该自动 dispatch
   - 触发条件：`handle_manager_dispatched()` 监听 `ManagerDispatched` event
   - 但 review 完成后是否触发该 event？需要验证

3. **竞态条件**
   - `_process_review_sync_result()` 写 audit_ref
   - no-op gate 读取 after_state
   - 如果 GitHub label 更新延迟，可能导致误判

**调试建议**：
```bash
# 查看 review 完成后的事件
tail -f temp/logs/orchestra/events.log | grep -E "review|manager|state"

# 检查 issue label
gh issue view {n} --json labels,state

# 查看 handoff/audit 记录
ls temp/logs/issues/issue-{n}/
cat temp/logs/issues/issue-{n}/reviewer.async.log
```

---

## 修复方案

### 修复 A-1: 增强 `handle_manager_dispatched` 错误处理

**目标**：当 `build_manager_request()` 返回 None 时，明确失败原因并通知用户。

**修改文件**：`src/vibe3/domain/handlers/issue_state_dispatch.py`

**修改内容**：

```python
if request is None:
    logger.bind(
        domain="issue_state_dispatch_handler",
        role="manager",
        issue_number=event.issue_number,
    ).error("Failed to prepare role execution request")
    
    # ✅ 新增：显式失败处理
    from vibe3.services.issue_failure_service import fail_manager_issue
    
    fail_manager_issue(
        issue_number=event.issue_number,
        reason="Manager dispatch failed: build_manager_request returned None. "
               "Possible causes: flow creation failed, capacity reached, or branch error.",
        actor="orchestra:issue_state_dispatch",
    )
    return
```

---

### 修复 A-2: `FlowManager.create_flow_for_issue` 返回详细错误信息

**目标**：让上层调用者知道具体失败原因。

**修改文件**：`src/vibe3/execution/flow_dispatch.py`

**方案**：修改返回类型为 `tuple[dict | None, str | None]` 或抛出具体的异常类型。

---

### 修复 A-3: 容量检查时优雅降级

**当前问题**：容量满时直接抛异常，导致 issue 冻结。

**修改建议**：

```python
if active_count >= self.config.max_concurrent_flows:
    # ✅ 不抛异常，返回 None 并记录日志
    logger.bind(
        domain="flow_dispatch",
        issue=issue.number,
        active_count=active_count,
        limit=self.config.max_concurrent_flows,
    ).warning("Manager capacity reached, deferring flow creation")
    return None  # 让上层决定是否 block 或重试
```

---

## 调试建议

### 验证步骤

1. **复现路径**：
   ```bash
   # 手动触发 manager dispatch
   uv run python src/vibe3/cli.py serve start --debug
   
   # 观察日志
   tail -f temp/logs/orchestra/events.log
   ```

2. **检查点**：
   - `handle_manager_dispatched` 是否被调用
   - `build_manager_request` 返回值
   - `create_flow_for_issue` 是否抛异常
   - issue label 是否变化

3. **证据收集**：
   ```bash
   uv run python src/vibe3/cli.py task status --all
   uv run python src/vibe3/cli.py flow show
   gh issue view {n} --json labels,state
   ```

---

## 下一步

1. ✅ 已定位 Bug A 根因
2. ⏳ 实现修复 A-1（增强错误处理）
3. ⏳ 实现修复 A-3（容量检查优雅降级）
4. ⏳ 验证 Bug B（review 状态收口）
5. ⏳ 测试修复效果

---

**创建者**: opencode  
**日期**: 2026-04-20  
**分支**: `debug/issue-481-serve-breakpoints`
