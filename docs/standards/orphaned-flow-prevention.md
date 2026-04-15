# Orphaned Flow Detection and Prevention

## 定义

**孤儿流（Orphaned Flow）**：数据库中存在 flow_state 记录（flow_status=active），但对应的 git 分支已不存在。

## 根因分析

### 问题场景

Issue #324 的实际时间线（来自 `vibe3 flow show task/issue-324`）：

```
2026-04-14 12:05  flow_auto_aborted  system
  Branch 'task/issue-324' no longer exists locally

2026-04-14 13:04  flow_reactivated  AI Agent
  Flow reactivated  ← 问题触发点

2026-04-14 13:44  manager_aborted  orchestra:manager
  Failed to resolve permanent worktree for manager:324
  （此后 15 次重复失败）
```

### 产生机制

1. **分支删除**：
   - `vibe3 task resume --failed` 调用 `reset_task_scene`
   - 正确删除 git 分支 + 数据库记录

2. **手动重新激活**：
   - AI Agent 手动调用 `reactivate_flow`
   - 更新数据库状态为 `active`
   - **但没有重建 git 分支**

3. **dispatch 循环失败**：
   - `_is_reusable_auto_flow` 认为记录可复用（缺少 git 分支检查）
   - `create_flow_for_issue` 直接返回孤儿记录
   - `resolve_manager_cwd` → `acquire_issue_worktree` → `git worktree add` 失败
   - 异步 dispatch 静默失败，下一 tick 重复

## 预防措施

### 代码修复

**位置**：[src/vibe3/execution/flow_dispatch.py:46-75](src/vibe3/execution/flow_dispatch.py#L46-L75)

```python
def _is_reusable_auto_flow(self, flow: dict[str, object], issue_number: int) -> bool:
    branch = str(flow.get("branch") or "").strip()
    canonical_branch = self.issue_flow_service.canonical_branch_name(issue_number)

    if branch != canonical_branch:
        return False

    # ✅ Guard against orphaned flow records
    if not self.git.branch_exists(branch):
        logger.warning(f"Flow branch '{branch}' missing in git — rejecting")
        return False

    return str(flow.get("flow_status") or "active") not in {
        "done",
        "aborted",
        "stale",
    }
```

**效果**：
- 孤儿记录被拒绝 → 返回 False
- `create_flow_for_issue` 调用 `_rebuild_stale_canonical_flow`
- `_rebuild_stale_canonical_flow` 先创建分支，再创建 worktree

### 正确处理流程

当发现孤儿流时，**不要手动 `reactivate_flow`**，应：

1. **标记为 stale**（系统自动）：
   ```bash
   vibe3 flow mark-stale task/issue-XXX
   ```

2. **让系统重建**（下一个 tick）：
   - `_rebuild_stale_canonical_flow` 自动重建分支
   - 正确创建 worktree
   - 启动 manager

## 边界条件

### `reset_task_scene` 的职责

[source](src/vibe3/services/task_resume_operations.py#L94-L123)

```python
def reset_task_scene(self, branch: str, worktree_path: str | None = None) -> None:
    # ... 删除 worktree ...
    self.git_client.delete_branch(branch, force=True, skip_if_worktree=True)
    HandoffService(...).clear_handoff_for_branch(branch)
    self.flow_service.delete_flow(branch)  # ← ✅ 正确删除数据库记录
```

**关键点**：
- 删除分支和数据库记录必须同步
- 当前实现正确，无问题

### Handler 异常传播

[source](src/vibe3/domain/handlers/dispatch.py#L93-L163)

**修复前**：
```python
except Exception as exc:
    logger.exception(f"Planner dispatch failed: {exc}")
    # ❌ 异常被吞掉，事件系统不知道失败
```

**修复后**：
```python
except Exception as exc:
    logger.exception(f"Planner dispatch failed: {exc}")
    raise  # ← ✅ 向上传播，让事件系统处理
```

## 相关文档

- [Flow Service](../../v3/architecture/flow-service.md)
- [Execution Coordinator](../../v3/architecture/coordinator.md)
- [Task Resume Operations](../../v3/operations/task-resume.md)

## 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2026-04-15 | Issue #324 孤儿流诊断与修复记录 |