---
document_type: guide
title: "PR #377 优化指引"
target_pr: 377
status: draft
author: "Claude"
created: "2026-03-30"
---

# PR #377 优化指引

PR #377 (feat: add temporary worktree cleanup service) 质量较好，engine/service
分离清晰，已提供 GitClient 通用方法给主干。以下是可优化点。

## 1. 消除 WorktreeInfo 构造重复（优先级：高）

`worktree_cleanup.py` 中 `_cleanup_for_branch()` 和 `_run_ttl_gc()` 有
几乎相同的 WorktreeInfo 构造逻辑（~20 行重复）。

**建议**：提取为 `_build_worktree_infos()` 私有方法：

```python
def _build_worktree_infos(
    self,
    worktree_tuples: list[tuple[str, str]],
) -> list[WorktreeInfo]:
    """从 GitClient.list_worktrees() 结果构造 WorktreeInfo 列表。"""
    result = []
    for wt_path_str, branch_ref in worktree_tuples:
        path = Path(wt_path_str).resolve()
        is_main = self._repo_path == path
        branch_name = branch_ref.removeprefix("refs/heads/")
        git_marker = path / ".git"
        if git_marker.exists():
            mtime = git_marker.stat().st_mtime
        else:
            mtime = path.stat().st_mtime if path.exists() else 0.0
        result.append(WorktreeInfo(
            path=path,
            branch_ref=branch_ref,
            branch_name=branch_name,
            is_main=is_main,
            is_dirty=False,
            mtime_seconds=mtime,
        ))
    return result
```

`_cleanup_for_branch()` 和 `_run_ttl_gc()` 各调用一次此方法，消除重复。

## 2. 复用或明确 engine 的 parse_worktree_info（优先级：中）

engine 中已有 `parse_worktree_info()` 函数，service 没有使用它，而是
自己从 `list_worktrees()` 元组构造 WorktreeInfo。两条路径产生相同的数据
结构但代码不同，增加维护负担。

**建议**：
- 若选择 service 的 `_build_worktree_infos()` 方案（优化点 #1），
  在 engine 的 `parse_worktree_info()` 上加 docstring 说明其用途
  （仅用于兼容测试 / porcelain output 解析），避免混淆
- 长期目标：统一为一条路径

## 3. 删除 DEPRECATED 方法（优先级：高）

`_list_worktrees_porcelain()` 和 `_is_worktree_clean()` 标记了 `DEPRECATED`，
仅为旧测试兼容保留。

**建议**：
- 更新测试，直接 mock `self._git_client.list_worktrees()` 和
  `self._git_client.is_worktree_clean()`
- 删除这两个 DEPRECATED 方法，减少公共表面积和维护负担

更新后的 test mock 示例：

```python
# 旧：mock DEPRECATED 方法
with patch.object(service, "_list_worktrees_porcelain", return_value="..."):

# 新：mock git_client 方法（更直接，与实现一致）
with patch.object(service._git_client, "list_worktrees", return_value=[...]):
```

## 4. 删除本地分支（优先级：中）

当前 worktree 清理只删除 worktree 目录，不删除关联的本地分支。
PR merged 后远程分支通常被 GitHub 自动删除，但本地分支残留。

**建议**：在 DELETE 决策执行成功后，尝试删除对应的本地分支：

```python
async def _execute_decisions(self, decisions: list[CleanupDecision]) -> None:
    ...
    for d in decisions:
        if d.action == CleanupAction.DELETE:
            success = await loop.run_in_executor(
                self._executor,
                lambda p=d.worktree.path: self._remove_worktree(p),
            )
            if success:
                # 删除本地分支（忽略失败，不影响主流程）
                await loop.run_in_executor(
                    self._executor,
                    lambda b=d.worktree.branch_name: self._try_delete_branch(b),
                )

def _try_delete_branch(self, branch_name: str) -> None:
    """尝试删除本地分支，失败时静默忽略。"""
    try:
        self._git_client.delete_branch(branch_name, force=True)
    except Exception as exc:
        logger.bind(domain="orchestra").debug(
            f"Could not delete branch '{branch_name}': {exc}"
        )
```

注意：需确认 `GitClient.delete_branch()` 有 `skip_if_worktree` 保护。

## 5. _execute_decisions 日志优化（优先级：低）

当前每个 decision 都调用 `logger.bind(...)` 创建新实例，在大量 worktree 时产生
冗余对象。

**建议**：提取公共日志绑定：

```python
async def _execute_decisions(self, decisions: list[CleanupDecision]) -> None:
    log = logger.bind(domain="orchestra", action="worktree_cleanup")
    prefix = "[DRY-RUN] " if self.config.cleanup.dry_run else ""

    for d in decisions:
        entry_log = log.bind(path=str(d.worktree.path))
        if d.action == CleanupAction.DELETE:
            entry_log.info(f"{prefix}Delete: {d.reason}")
        else:
            entry_log.debug(f"{prefix}Skip: {d.reason}")
```

## 6. 测试 fixture 提取（优先级：低）

`test_worktree_cleanup_service.py` 的 mock setup 在多个测试中重复。
可考虑将通用的 executor/git_client mock 提取为 conftest fixture，
减少测试样板代码。

## 优先级汇总

| 项目 | 优先级 | 影响 |
|------|--------|------|
| #1 消除 WorktreeInfo 构造重复 | 高 | 减少维护负担，DRY 原则 |
| #3 删除 DEPRECATED 方法 | 高 | 减少代码表面积，测试更直接 |
| #4 删除本地分支 | 中 | 完善清理闭环，避免分支积累 |
| #2 统一 parse 路径 | 中 | 减少混淆 |
| #5 日志优化 | 低 | 微优化，大量 worktree 时略有改善 |
| #6 测试 fixture | 低 | 改善测试可读性 |

**建议**：在合并前至少完成 #1 和 #3，其余可作为 follow-up。
