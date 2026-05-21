# Orchestra Status Snapshot Race Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## 问题背景

### 根因分析

在 `tick #51` 执行过程中，`/status` HTTP 端点触发了 SQLite 并发异常：

```
sqlite3.InterfaceError: bad parameter or other API misuse
sqlite3.OperationalError: cannot commit - no transaction is active
```

**根因链路**：

1. `/status` 端点将 `snapshot()` 提交到线程池执行
   - 参考：`src/vibe3/server/registry.py:129`

2. `snapshot()` 对每个 issue 调用 `get_pr_for_issue()`
   - 参考：`src/vibe3/services/orchestra_status_service.py:278`

3. `get_pr_for_issue()` 创建新的 `PRService`，调用 `get_branch_pr_status()`
   - 参考：`src/vibe3/orchestra/flow_dispatch.py:232`

4. `get_branch_pr_status()` 刷新 recent PR cache，并将 PR 信息回写到 `flow_context_cache`
   - 参考：`src/vibe3/services/pr_service.py:142`

5. 回写操作访问共享 SQLite 连接
   - 参考：`src/vibe3/clients/sqlite_context_cache_repo.py:16`

6. SQLite 基础层使用"进程级单连接 + `check_same_thread=False`"，只在建连时加锁，未对实际读写加锁
   - 参考：`src/vibe3/clients/sqlite_base.py:15`

**问题本质**：这不是数据损坏，而是并发访问同一个 SQLite 连接导致事务状态混乱。多个线程共用一个连接时，事务可能被其他线程修改，导致 "no transaction is active" 错误。

**历史记录**：`2026-05-21 03:27:50` 已经出现过同样的 `/status -> snapshot -> PRService -> sqlite_context_cache` 链路报错。

---

## 解决方案

### 目标

修复 `/status` 在运行中触发的 SQLite 并发异常：
1. 避免状态读取路径回写 `flow_context_cache`
2. 移除 `snapshot()` 的逐 issue PR 查询

### 架构设计

**核心思路**：

1. **为 `PRService` 增加显式的 `sync_context_cache` 开关**
   - 默认保持现状（向后兼容）
   - 只读状态查询时关闭 SQLite context cache 回写

2. **`OrchestraStatusService.snapshot()` 改为批量只读模式**
   - 先收集所有 flow branch
   - 一次性批量读取 branch→PR 映射
   - 用批量结果填充 `pr_number`
   - 不再对每个 issue 调用 `get_pr_for_issue()`

### 技术栈

- Python 3.12
- FastAPI/Uvicorn
- SQLite
- pytest
- `unittest.mock`

---

## 文件映射

### 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `src/vibe3/services/pr_service.py` | 为 recent PR cache 刷新和 branch PR 查询增加只读模式开关 |
| `src/vibe3/services/orchestra_status_service.py` | 将 snapshot PR 解析改成批量只读路径 |
| `tests/vibe3/services/test_pr_lifecycle_cache.py` | 增加"关闭 context cache sync 时不写 SQLite"回归测试 |
| `tests/vibe3/services/test_orchestra_status_snapshot.py` | 增加"snapshot 不再逐 issue 调 PR fallback"回归测试 |

---

## 实现任务

### Task 1: 为 PRService 增加失败回归测试

**目标**：验证 `refresh_recent_pr_cache` 可以跳过 context cache 同步

**文件**：`tests/vibe3/services/test_pr_lifecycle_cache.py`

#### Step 1: 写失败测试

```python
def test_refresh_recent_pr_cache_can_skip_context_cache_sync() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "repo"
        repo_path.mkdir()
        git_dir = repo_path / ".git"
        git_dir.mkdir()
        (git_dir / "vibe3").mkdir()

        db_path = repo_path / "test.db"
        store = SQLiteClient(db_path=str(db_path))
        store.update_flow_state("feature-readonly", flow_slug="readonly")

        cache = RecentPRCache(repo_path)
        cache._save_cache(
            {
                "last_sync": datetime.now(timezone.utc).isoformat(),
                "prs": {
                    "feature-readonly": {
                        "number": 404,
                        "title": "Readonly PR",
                        "state": "OPEN",
                        "draft": False,
                        "url": "https://github.com/test/pr/404",
                        "head_branch": "feature-readonly",
                        "base_branch": "main",
                        "merged_at": None,
                    }
                },
            }
        )

        github_client = MagicMock()
        git_client = MagicMock()
        git_client.get_git_common_dir.return_value = str(git_dir)

        service = PRService(
            github_client=github_client,
            git_client=git_client,
            store=store,
        )

        with patch.object(service, "_sync_branch_context_cache") as sync_mock:
            branch_to_pr = service.refresh_recent_pr_cache(sync_context_cache=False)

        sync_mock.assert_not_called()
        assert branch_to_pr["feature-readonly"].number == 404
        assert store.get_flow_context_cache("feature-readonly") is None
```

#### Step 2: 运行单测，确认先失败

```bash
uv run pytest tests/vibe3/services/test_pr_lifecycle_cache.py::test_refresh_recent_pr_cache_can_skip_context_cache_sync -q
```

**预期结果**：FAIL，报 `unexpected keyword argument 'sync_context_cache'`

---

### Task 2: 实现 PRService 的只读 cache 刷新开关

**目标**：为 `refresh_recent_pr_cache` 和相关方法增加 `sync_context_cache` 参数

**文件**：
- `src/vibe3/services/pr_service.py`
- `tests/vibe3/services/test_pr_lifecycle_cache.py`

#### Step 1: 修改方法签名并按开关控制写入

```python
def refresh_recent_pr_cache(
    self,
    *,
    force: bool = False,
    limit: int = 50,
    max_age_minutes: int = 10,
    sync_context_cache: bool = True,
) -> dict[str, PRResponse]:
    if force or not self.recent_pr_cache.is_fresh(max_age_minutes=max_age_minutes):
        self.recent_pr_cache.sync(self.github_client, limit=limit)

    cached = self.recent_pr_cache.get_all_branch_prs()
    branch_to_pr: dict[str, PRResponse] = {}
    for branch, data in cached.items():
        if not isinstance(data, dict):
            continue
        pr = self._cache_entry_to_pr(branch, data)
        if pr is not None:
            branch_to_pr[branch] = pr

    self._recent_pr_cache_map = branch_to_pr
    if sync_context_cache:
        self._sync_branch_context_cache(branch_to_pr)
    return branch_to_pr
```

#### Step 2: 透传到 open/status 查询路径

```python
def refresh_open_pr_cache(
    self,
    *,
    force: bool = False,
    limit: int = 50,
    max_age_minutes: int = 10,
    sync_context_cache: bool = True,
) -> dict[str, PRResponse]:
    recent = self.refresh_recent_pr_cache(
        force=force,
        limit=limit,
        max_age_minutes=max_age_minutes,
        sync_context_cache=sync_context_cache,
    )
    return {branch: pr for branch, pr in recent.items() if pr.state == PRState.OPEN}

def get_branch_pr_status(
    self,
    branch: str,
    *,
    refresh: bool = True,
    max_age_minutes: int = 10,
    limit: int = 50,
    sync_context_cache: bool = True,
) -> PRResponse | None:
    cache = (
        self.refresh_recent_pr_cache(
            force=False,
            limit=limit,
            max_age_minutes=max_age_minutes,
            sync_context_cache=sync_context_cache,
        )
        if refresh
        else self._recent_pr_cache_map
    )
    ...
    if sync_context_cache:
        self._sync_branch_context_cache({branch: pr})
    return pr
```

#### Step 3: 运行测试，确认通过且旧行为不回归

```bash
uv run pytest tests/vibe3/services/test_pr_lifecycle_cache.py -q
```

**预期结果**：PASS，包含新测试与现有 cache 同步测试全部通过

---

### Task 3: 为 snapshot 批量 PR 解析增加失败回归测试

**目标**：验证 snapshot 不再逐 issue 调用 PR fallback

**文件**：`tests/vibe3/services/test_orchestra_status_snapshot.py`

#### Step 1: 扩充 import 并添加失败测试

```python
from unittest.mock import MagicMock, patch

from vibe3.models.pr import PRResponse, PRState
```

```python
def test_snapshot_batches_pr_lookup_without_per_issue_branch_fallback(self):
    github = MagicMock()
    github.list_issues.return_value = [
        {
            "number": 501,
            "title": "Issue one",
            "assignees": [{"login": "manager-bot"}],
            "labels": [{"name": "state/in-progress"}],
            "milestone": None,
            "body": "",
        },
        {
            "number": 502,
            "title": "Issue two",
            "assignees": [{"login": "manager-bot"}],
            "labels": [{"name": "state/review"}],
            "milestone": None,
            "body": "",
        },
    ]

    config = OrchestraConfig(manager_usernames=["manager-bot"], repo="test/repo")
    orchestrator = MagicMock()
    orchestrator.get_flow_for_issue.side_effect = [
        {"branch": "task/issue-501"},
        {"branch": "task/issue-502"},
    ]
    orchestrator.get_pr_for_issue.side_effect = AssertionError(
        "snapshot should not call per-issue PR fallback"
    )

    service = OrchestraStatusService(
        config=config,
        github=github,
        orchestrator=orchestrator,
    )

    branch_to_pr = {
        "task/issue-501": PRResponse(
            number=9001,
            title="PR one",
            body="",
            state=PRState.OPEN,
            head_branch="task/issue-501",
            base_branch="main",
            url="https://github.com/test/pr/9001",
            draft=False,
            is_ready=True,
            ci_passed=False,
            created_at=None,
            updated_at=None,
            merged_at=None,
            metadata=None,
        )
    }

    with patch("vibe3.services.orchestra_status_service.PRService") as pr_service_cls:
        pr_service_cls.return_value.refresh_recent_pr_cache.return_value = branch_to_pr
        snapshot = service.snapshot()

    assert [entry.number for entry in snapshot.active_issues] == [502, 501]
    assert {entry.number: entry.pr_number for entry in snapshot.active_issues} == {
        501: 9001,
        502: None,
    }
    orchestrator.get_pr_for_issue.assert_not_called()
    pr_service_cls.return_value.refresh_recent_pr_cache.assert_called_once_with(
        sync_context_cache=False
    )
```

#### Step 2: 运行单测，确认先失败

```bash
uv run pytest tests/vibe3/services/test_orchestra_status_snapshot.py::TestSnapshotIssuePoolBoundary::test_snapshot_batches_pr_lookup_without_per_issue_branch_fallback -q
```

**预期结果**：FAIL，当前实现会调用 `get_pr_for_issue()`，触发断言

---

### Task 4: 实现 snapshot 的批量只读 PR 解析

**目标**：将 snapshot 改为先收集 flow branch，再批量读取 PR 映射

**文件**：
- `src/vibe3/services/orchestra_status_service.py`
- `tests/vibe3/services/test_orchestra_status_snapshot.py`

#### Step 1: 引入 `PRService`，在 snapshot 中先收集 flow，再批量取 PR 映射

```python
from typing import TYPE_CHECKING, Any, cast

from vibe3.clients.protocols import GitHubClientProtocol
from vibe3.services.pr_service import PRService
```

```python
issue_rows: list[dict[str, Any]] = []
flow_branches: set[str] = set()

for issue in issues:
    number = issue.get("number")
    if not number:
        continue

    flow = self._orchestrator.get_flow_for_issue(number)
    if flow and not is_orchestra_managed_flow_branch(flow.get("branch")):
        continue

    flow_branch = flow.get("branch") if flow else None
    if flow_branch:
        flow_branches.add(str(flow_branch))

    issue_rows.append(
        {
            "issue": issue,
            "flow": flow,
            "flow_branch": flow_branch,
        }
    )

branch_to_pr: dict[str, Any] = {}
if flow_branches:
    try:
        pr_service = PRService(
            github_client=cast(GitHubClientProtocol, self._github),
            git_client=self._git,
            store=getattr(self._orchestrator, "store", None),
        )
        recent = pr_service.refresh_recent_pr_cache(sync_context_cache=False)
        branch_to_pr = {
            branch: pr for branch, pr in recent.items() if branch in flow_branches
        }
    except Exception as exc:
        log.warning(f"Failed to batch hydrate PR status: {exc}")
```

#### Step 2: 用批量结果填充 `pr_number`，不再调用 `get_pr_for_issue()`

```python
for row in issue_rows:
    issue = row["issue"]
    flow = row["flow"]
    flow_branch = row["flow_branch"]

    ...
    stored_pr_number = int(flow["pr_number"]) if flow and flow.get("pr_number") else None
    cached_pr = branch_to_pr.get(flow_branch) if flow_branch else None
    pr_number = cached_pr.number if cached_pr else stored_pr_number
    has_pr = pr_number is not None
    ...
```

#### Step 3: 跑两组测试确认实现完成

```bash
uv run pytest tests/vibe3/services/test_orchestra_status_snapshot.py::TestSnapshotIssuePoolBoundary::test_snapshot_batches_pr_lookup_without_per_issue_branch_fallback -q
```

**预期结果**：PASS

```bash
uv run pytest tests/vibe3/services/test_pr_lifecycle_cache.py tests/vibe3/services/test_orchestra_status_snapshot.py -q
```

**预期结果**：PASS

---

### Task 5: 手工回归与两步提交

**目标**：验证修复有效并按项目规范提交

**文件**：
- `src/vibe3/services/pr_service.py`
- `src/vibe3/services/orchestra_status_service.py`
- `tests/vibe3/services/test_pr_lifecycle_cache.py`
- `tests/vibe3/services/test_orchestra_status_snapshot.py`

#### Step 1: 在 live serve 环境做一次手工回归

```bash
uv run python src/vibe3/cli.py status
```

**预期结果**：
- 能正常返回状态
- `temp/logs/orchestra/events.log` 不再出现：
  - `Exception in ASGI application`
  - `sqlite3.InterfaceError`
  - `cannot commit - no transaction is active`

#### Step 2: 做项目要求的临时提交触发质量门

```bash
git add src/vibe3/services/pr_service.py \
        src/vibe3/services/orchestra_status_service.py \
        tests/vibe3/services/test_pr_lifecycle_cache.py \
        tests/vibe3/services/test_orchestra_status_snapshot.py
git commit -m "temp: verify orchestra status snapshot race fix"
```

#### Step 3: 回退临时提交并做正式分组提交

```bash
git reset --soft HEAD~1
git status --short
git commit -m "fix: avoid context-cache writes from orchestra status snapshot"
```

---

## 范围说明

这份计划先修复已确认的 `/status` 触发路径，**不包含** `src/vibe3/clients/sqlite_base.py` 的全局连接模型重构。

如果这个补丁合入后，别的 HTTP/CLI 路径仍出现同类 SQLite 事务错乱，再单开第二份计划做"per-thread/per-operation SQLite connection" 硬化。

---

## 参考文档

- [CLAUDE.md](../../CLAUDE.md) - 项目上下文与硬规则
- [SOUL.md](../../SOUL.md) - 项目宪法
- [docs/standards/glossary.md](../standards/glossary.md) - 术语真源
- [docs/standards/agent-workflow-standard.md](../standards/agent-workflow-standard.md) - Agent 工作流规范
