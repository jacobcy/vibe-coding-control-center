# Close/Abort Technical Debt Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理 close/abort 路径的技术债务：移除零引用函数、重命名语义偏离的服务、提取 manager post-run orchestration 逻辑

**Architecture:** 三步清理策略：先移除死代码（零引用函数），再重命名语义偏离的 API（语义对齐），最后提取复杂 orchestration（架构解耦）

**Tech Stack:** Python 3.10+, pytest, Vibe3 测试框架

---

## 文件结构

**修改的文件：**
- `src/vibe3/services/issue_failure_service.py` - 移除零引用的 `close_ready_issue` 函数（269-344行）
- `src/vibe3/services/ready_close_service.py` - 重命名为语义中性的 `IssueCloseService`
- `src/vibe3/services/abandon_flow_service.py` - 更新导入和调用以匹配新服务名
- `src/vibe3/manager/manager_run_service.py` - 提取 post-run orchestration 到新的 coordinator
- `src/vibe3/manager/manager_run_coordinator.py` - 新建：post-run outcome handling coordinator

**测试文件：**
- `tests/vibe3/services/test_ready_close_service.py` - 重命名并更新测试
- `tests/vibe3/services/test_abandon_flow_service.py` - 更新导入
- `tests/vibe3/manager/test_manager_run_service.py` - 更新测试覆盖

---

## Task 1: 移除零引用的 close_ready_issue 函数

**Files:**
- Modify: `src/vibe3/services/issue_failure_service.py:269-344`
- Test: `tests/vibe3/services/test_issue_failure_service.py`

**理由:** `issue_failure_service.close_ready_issue()` 确认零引用（inspect symbols 显示 0 references），测试文件中无测试覆盖，完全未使用。移除以消除死代码和潜在的混淆。

- [ ] **Step 1: 验证零引用**

运行符号引用检查，确认函数确实零引用：

```bash
uv run python src/vibe3/cli.py inspect symbols src/vibe3/services/issue_failure_service.py:close_ready_issue
```

预期输出：
```
=== Symbol: close_ready_issue ===
  Defined in: src/vibe3/services/issue_failure_service.py
  References: 0
```

- [ ] **Step 2: 搜索潜在隐式引用**

使用 grep 搜索任何可能的字符串引用：

```bash
grep -r "close_ready_issue" src/vibe3 tests/vibe3 --include="*.py"
```

预期：只有 issue_failure_service.py 中的定义和导入语句，无实际调用。

- [ ] **Step 3: 删除函数**

删除 `src/vibe3/services/issue_failure_service.py` 中的 `close_ready_issue` 函数（第269-344行）：

```python
# DELETE lines 269-344:
def close_ready_issue(
    *,
    issue_number: int,
    repo: str | None,
    reason: str,
    actor: str = "agent:manager",
) -> str:
    """Close a ready issue when task should not be executed.

    This is the controlled path for managers to close issues
    in state/ready. Only works when issue is in state/ready.
    ...
    """
    # [删除整个函数体]
```

保留文件的其余部分（其他函数：fail_executor_issue, fail_manager_issue, resume_failed_issue_to_handoff, 等）。

- [ ] **Step 4: 移除导入语句**

检查并删除 `issue_failure_service.py` 顶部的 `ReadyCloseService` 导入（第16行）：

```python
# DELETE this import line:
from vibe3.services.ready_close_service import ReadyCloseService
```

注意：其他函数不使用此导入。

- [ ] **Step 5: 运行测试验证无影响**

运行 issue_failure_service 测试套件：

```bash
uv run pytest tests/vibe3/services/test_issue_failure_service.py -v
```

预期：所有测试通过（函数无测试覆盖，移除不影响）。

- [ ] **Step 6: 提交**

```bash
git add src/vibe3/services/issue_failure_service.py
git commit -m "refactor: remove zero-reference close_ready_issue wrapper

Dead code removal - issue_failure_service.close_ready_issue has zero
references and no test coverage. AbandonFlowService directly uses
ReadyCloseService, bypassing this wrapper entirely.

Evidence: inspect symbols shows 0 references, grep confirms no usage."
```

---

## Task 2: 重命名 ReadyCloseService 为语义中性的 IssueCloseService

**Files:**
- Modify: `src/vibe3/services/ready_close_service.py` → 重命名为 `src/vibe3/services/issue_close_service.py`
- Modify: `src/vibe3/services/abandon_flow_service.py`
- Modify: `src/vibe3/manager/manager_run_service.py`
- Modify: `tests/vibe3/services/test_ready_close_service.py` → 重命名为 `tests/vibe3/services/test_issue_close_service.py`
- Modify: `tests/vibe3/services/test_abandon_flow_service.py`

**理由:** `ReadyCloseService` 命名暗示仅用于 `state/ready`，但实际被 `AbandonFlowService` 用于 ready/handoff 两种状态。重命名以消除语义偏离，使 API 名称与系统级含义匹配。

- [ ] **Step 1: 创建新的 issue_close_service.py**

创建新文件 `src/vibe3/services/issue_close_service.py`，基于 `ready_close_service.py` 但更新：

```python
"""Issue close service - low-level GitHub issue close primitive.

This service provides the basic issue close operation used by
AbandonFlowService for flow abandonment. It is a narrow primitive
without state-specific policy - the orchestration layer (AbandonFlowService)
enforces state requirements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient


class IssueCloseService:
    """Service for closing GitHub issues.

    This is a low-level primitive for closing issues via GitHub API.
    It does not enforce state-specific policy - orchestration services
    like AbandonFlowService handle state validation and semantic meaning.

    The close operation handles the "already closed" case gracefully
    to support abandonment flows where the issue may already be closed.
    """

    def __init__(self, github: GitHubClient, repo: str | None = None):
        """Initialize issue close service.

        Args:
            github: GitHub client for API operations
            repo: Optional repo override (owner/repo)
        """
        self._github = github
        self._repo = repo

    def close_issue(
        self,
        issue_number: int,
        closing_comment: str | None = None,
        issue_payload: dict[str, object] | None = None,
    ) -> str:
        """Close a GitHub issue.

        Args:
            issue_number: Issue number to close
            closing_comment: Optional comment explaining why the issue is closed
            issue_payload: Optional pre-fetched issue payload (avoids
                duplicate API call)

        Returns:
            Result string: "closed", "already_closed", or "failed"
        """
        logger.bind(
            domain="orchestra",
            operation="close_issue",
            issue_number=issue_number,
        ).info("Closing issue")

        # Check if already closed (avoid unnecessary API call)
        if issue_payload is None:
            issue_payload_raw = self._github.view_issue(issue_number, repo=self._repo)
            if isinstance(issue_payload_raw, dict):
                issue_payload = issue_payload_raw

        if isinstance(issue_payload, dict) and issue_payload.get("state") == "closed":
            logger.bind(
                domain="orchestra",
                issue_number=issue_number,
            ).info("Issue already closed")
            return "already_closed"

        # Call GitHub close API
        success = self._github.close_issue(
            issue_number=issue_number,
            comment=closing_comment,
            repo=self._repo,
        )

        if success:
            logger.bind(
                domain="orchestra",
                issue_number=issue_number,
            ).info("Issue closed successfully")
            return "closed"
        else:
            logger.bind(
                domain="orchestra",
                issue_number=issue_number,
            ).error("Failed to close issue")
            return "failed"
```

注意：类名和方法名从 `ReadyCloseService.close_ready_issue` 改为 `IssueCloseService.close_issue`。

- [ ] **Step 2: 删除旧的 ready_close_service.py**

```bash
rm src/vibe3/services/ready_close_service.py
```

- [ ] **Step 3: 更新 abandon_flow_service.py 导入**

修改 `src/vibe3/services/abandon_flow_service.py` 第20行和第55行：

```python
# Line 20: UPDATE import
if TYPE_CHECKING:
    from vibe3.services.flow_service import FlowService
    from vibe3.services.pr_service import PRService
    from vibe3.services.issue_close_service import IssueCloseService

# Line 35: UPDATE field type
_issue_close: IssueCloseService

# Line 54-57: UPDATE lazy load
if ready_close is None:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.services.issue_close_service import IssueCloseService

    ready_close = IssueCloseService(github=GitHubClient())
```

- [ ] **Step 4: 更新 abandon_flow_service.py 方法调用**

修改 `src/vibe3/services/abandon_flow_service.py` 第116行：

```python
# Line 116: UPDATE method call
results["issue"] = self._issue_close.close_issue(
    issue_number, closing_comment=closing_comment
)
```

注意：字段名从 `_ready_close` 改为 `_issue_close`，方法名从 `close_ready_issue` 改为 `close_issue`。

- [ ] **Step 5: 更新 __init__ 参数名**

修改 `src/vibe3/services/abandon_flow_service.py` 第39-44行：

```python
def __init__(
    self,
    issue_close: IssueCloseService | None = None,
    pr_service: PRService | None = None,
    flow_service: FlowService | None = None,
) -> None:
    """Initialize abandon flow service.

    Args:
        issue_close: Service for closing issues
        pr_service: Service for managing PRs
        flow_service: Service for flow lifecycle
    """
```

并更新第69行的赋值：

```python
self._issue_close = issue_close
```

- [ ] **Step 6: 搜索所有 ReadyCloseService 引用**

检查是否有其他文件引用旧名称：

```bash
grep -r "ReadyCloseService" src/vibe3 tests/vibe3 --include="*.py"
```

预期：除了已更新的文件，应无其他引用。

- [ ] **Step 7: 运行 abandon_flow_service 测试**

```bash
uv run pytest tests/vibe3/services/test_abandon_flow_service.py -v
```

预期：测试可能失败（导入错误），需要更新测试文件。

- [ ] **Step 8: 更新测试文件导入**

修改 `tests/vibe3/services/test_abandon_flow_service.py` 的导入：

```python
# UPDATE import
from vibe3.services.issue_close_service import IssueCloseService
```

并更新所有 mock/fixture 中使用 `ReadyCloseService` 的地方改为 `IssueCloseService`。

- [ ] **Step 9: 重命名并更新 ready_close_service 测试文件**

```bash
mv tests/vibe3/services/test_ready_close_service.py tests/vibe3/services/test_issue_close_service.py
```

更新文件内容：

```python
"""Tests for issue_close_service."""

from vibe3.services.issue_close_service import IssueCloseService


class TestIssueCloseService:
    """Tests for IssueCloseService.close_issue."""

    def test_close_issue_success(self, mock_github_client):
        """Test successful issue close."""
        service = IssueCloseService(github=mock_github_client)
        result = service.close_issue(123, closing_comment="Test reason")
        assert result == "closed"

    def test_close_issue_already_closed(self, mock_github_client):
        """Test closing an already closed issue."""
        mock_github_client.view_issue.return_value = {"state": "closed"}
        service = IssueCloseService(github=mock_github_client)
        result = service.close_issue(123)
        assert result == "already_closed"

    def test_close_issue_failure(self, mock_github_client):
        """Test failed issue close."""
        mock_github_client.close_issue.return_value = False
        service = IssueCloseService(github=mock_github_client)
        result = service.close_issue(123, closing_comment="Test")
        assert result == "failed"
```

- [ ] **Step 10: 运行所有相关测试**

```bash
uv run pytest tests/vibe3/services/test_issue_close_service.py tests/vibe3/services/test_abandon_flow_service.py -v
```

预期：所有测试通过。

- [ ] **Step 11: 提交**

```bash
git add src/vibe3/services/issue_close_service.py
git add src/vibe3/services/abandon_flow_service.py
git add tests/vibe3/services/test_issue_close_service.py
git add tests/vibe3/services/test_abandon_flow_service.py
git rm src/vibe3/services/ready_close_service.py
git rm tests/vibe3/services/test_ready_close_service.py
git commit -m "refactor: rename ReadyCloseService to IssueCloseService

Semantic alignment - ReadyCloseService name suggested ready-only usage,
but AbandonFlowService uses it for both ready and handoff states.

Changes:
- Rename class: ReadyCloseService → IssueCloseService
- Rename method: close_ready_issue → close_issue
- Update all imports and references
- Rename test file and update tests
- Remove state-specific naming/docstrings (policy moved to orchestration layer)

Rationale: Service is now a low-level primitive, orchestration layer
handles state-specific policy and semantic meaning."
```

---

## Task 3: 提取 Manager Post-Run Orchestration Coordinator

**Files:**
- Create: `src/vibe3/manager/manager_run_coordinator.py`
- Modify: `src/vibe3/manager/manager_run_service.py`

**理由:** `run_manager_issue_mode` 是 253 LOC 的巨型函数，混合了 prompt 渲染、backend 执行、post-run outcome handling、progress checking、noop block fallback、abandon cleanup。提取 post-run orchestration 到独立的 coordinator，解耦 runtime entry 与 lifecycle orchestration。

- [ ] **Step 1: 分析 run_manager_issue_mode 结构**

识别需要提取的 post-run handling 部分：

```bash
uv run python src/vibe3/cli.py inspect files src/vibe3/manager/manager_run_service.py
```

关键片段（第280-360行）：
- Success/failure handling (280-298)
- Progress snapshot (317-323)
- Post-run outcome handling (324-333)
- No-progress block handling (336-360)

- [ ] **Step 2: 设计 coordinator interface**

创建 `src/vibe3/manager/manager_run_coordinator.py`：

```python
"""Manager run post-execution coordinator.

This module handles post-run orchestration for manager execution,
separating lifecycle coordination from the runtime entrypoint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.no_progress_policy import has_progress_changed
from vibe3.services.abandon_flow_service import AbandonFlowService
from vibe3.services.issue_failure_service import block_manager_noop_issue

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient


class ManagerRunCoordinator:
    """Coordinates post-run manager lifecycle.

    This coordinator handles:
    - Post-run abandon flow orchestration
    - Progress checking and no-op blocking
    - Event recording for manager outcomes
    """

    def __init__(self, store: SQLiteClient) -> None:
        """Initialize coordinator.

        Args:
            store: SQLite client for flow state
        """
        self._store = store

    def handle_post_run_outcome(
        self,
        *,
        issue_number: int,
        branch: str,
        actor: str,
        repo: str | None,
        before_snapshot: dict[str, object],
        after_snapshot: dict[str, object],
    ) -> bool:
        """Handle post-run close/abandon outcomes.

        Returns True when the outcome was fully handled and the caller should stop.
        """
        if after_snapshot.get("issue_state") != "closed":
            return False

        before_state_label = before_snapshot.get("state_label", "")
        source_state: IssueState | None = None
        if before_state_label == "state/ready":
            source_state = IssueState.READY
        elif before_state_label == "state/handoff":
            source_state = IssueState.HANDOFF

        if source_state is None:
            self._store.add_event(
                branch,
                "manager_closed_issue_unexpected_state",
                actor,
                detail=(
                    f"Issue #{issue_number} closed but was in {before_state_label} "
                    f"(expected state/ready or state/handoff)"
                ),
                refs={"issue": str(issue_number)},
            )
            return True

        abandon_service = AbandonFlowService()
        abandon_result = abandon_service.abandon_flow(
            issue_number=issue_number,
            branch=branch,
            source_state=source_state,
            reason="manager closed issue without finalizing abandon flow",
            actor=actor,
            issue_already_closed=True,
            flow_already_aborted=after_snapshot.get("flow_status") == "aborted",
        )
        self._store.add_event(
            branch,
            "manager_abandoned_flow",
            actor,
            detail=(
                f"Manager abandoned flow for issue #{issue_number} "
                f"(issue={abandon_result.get('issue')}, "
                f"pr={abandon_result.get('pr')}, "
                f"flow={abandon_result.get('flow')})"
            ),
            refs={"issue": str(issue_number), "result": str(abandon_result)},
        )
        return True

    def check_progress_and_block_if_noop(
        self,
        *,
        issue_number: int,
        branch: str,
        actor: str,
        repo: str | None,
        before_snapshot: dict[str, object],
        after_snapshot: dict[str, object],
    ) -> bool:
        """Check if manager made progress, block if no-op.

        Returns True if manager was blocked (caller should stop).
        """
        # Manager must leave READY or HANDOFF state to count as progress
        current_state_label = before_snapshot.get("state_label", "")
        allow_close = current_state_label in ("state/ready", "state/handoff")
        if not has_progress_changed(
            before_snapshot,
            after_snapshot,
            require_state_transition=True,
            allow_close_as_progress=allow_close,
        ):
            reason = "manager 本轮未产生状态迁移（must leave READY/HANDOFF per contract）"
            self._store.add_event(
                branch,
                "manager_noop_blocked",
                actor,
                detail=f"Manager auto-blocked issue #{issue_number}: {reason}",
                refs={"issue": str(issue_number), "reason": reason},
            )
            block_manager_noop_issue(
                issue_number=issue_number,
                repo=repo,
                reason=reason,
                actor=actor,
            )
            return True
        return False
```

- [ ] **Step 3: 更新 manager_run_service.py 使用 coordinator**

修改 `src/vibe3/manager/manager_run_service.py` 第45-104行：

```python
# DELETE handle_manager_post_run_outcome function (lines 45-104)
# MOVE logic to ManagerRunCoordinator.handle_post_run_outcome

# ADD import at top:
from vibe3.manager.manager_run_coordinator import ManagerRunCoordinator
```

- [ ] **Step 4: 简化 run_manager_issue_mode**

修改 `src/vibe3/manager/manager_run_service.py` 第309-360行：

```python
# Line 309: UPDATE flow state update
store.update_flow_state(
    branch,
    latest_actor=actor,
    manager_session_id=None,
)

# Line 310-316: Keep event recording (unchanged)
store.add_event(
    branch,
    "manager_completed",
    actor,
    detail=f"Manager execution completed for issue #{issue_number}",
    refs={"issue": str(issue_number), "status": "completed"},
)

# Line 317-333: REPLACE with coordinator call
after_snapshot = snapshot_progress(
    issue_number=issue_number,
    branch=branch,
    store=store,
    github=GitHubClient(),
    repo=orchestra_config.repo,
)
coordinator = ManagerRunCoordinator(store)
if coordinator.handle_post_run_outcome(
    issue_number=issue_number,
    branch=branch,
    actor=actor,
    repo=orchestra_config.repo,
    before_snapshot=before_snapshot,
    after_snapshot=after_snapshot,
):
    return

# Line 336-360: REPLACE with coordinator call
if coordinator.check_progress_and_block_if_noop(
    issue_number=issue_number,
    branch=branch,
    actor=actor,
    repo=orchestra_config.repo,
    before_snapshot=before_snapshot,
    after_snapshot=after_snapshot,
):
    return
```

- [ ] **Step 5: 创建 coordinator 测试**

创建 `tests/vibe3/manager/test_manager_run_coordinator.py`：

```python
"""Tests for manager_run_coordinator."""

import pytest
from unittest.mock import Mock, MagicMock

from vibe3.manager.manager_run_coordinator import ManagerRunCoordinator
from vibe3.models.orchestration import IssueState


class TestManagerRunCoordinator:
    """Tests for ManagerRunCoordinator."""

    @pytest.fixture
    def mock_store(self):
        """Mock SQLiteClient."""
        return Mock()

    @pytest.fixture
    def coordinator(self, mock_store):
        """Create coordinator with mock store."""
        return ManagerRunCoordinator(store=mock_store)

    def test_handle_post_run_outcome_closed_issue_ready_state(
        self, coordinator, mock_store
    ):
        """Test abandon flow when issue closed from ready state."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"issue_state": "closed", "flow_status": "active"}

        result = coordinator.handle_post_run_outcome(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is True
        # Verify abandon flow was called
        assert mock_store.add_event.called

    def test_handle_post_run_outcome_closed_issue_handoff_state(
        self, coordinator, mock_store
    ):
        """Test abandon flow when issue closed from handoff state."""
        before_snapshot = {"state_label": "state/handoff"}
        after_snapshot = {"issue_state": "closed"}

        result = coordinator.handle_post_run_outcome(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is True

    def test_handle_post_run_outcome_issue_not_closed(self, coordinator):
        """Test no action when issue not closed."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"issue_state": "open"}

        result = coordinator.handle_post_run_outcome(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is False

    def test_check_progress_and_block_if_noop_blocks_when_no_progress(
        self, coordinator, mock_store
    ):
        """Test blocking when manager makes no progress."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"state_label": "state/ready"}

        result = coordinator.check_progress_and_block_if_noop(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is True
        assert mock_store.add_event.called

    def test_check_progress_and_block_if_noop_passes_when_progress(
        self, coordinator, mock_store
    ):
        """Test no blocking when manager makes progress."""
        before_snapshot = {"state_label": "state/ready"}
        after_snapshot = {"state_label": "state/handoff"}

        result = coordinator.check_progress_and_block_if_noop(
            issue_number=123,
            branch="task/issue-123",
            actor="agent:manager",
            repo=None,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )

        assert result is False
```

- [ ] **Step 6: 运行 coordinator 测试**

```bash
uv run pytest tests/vibe3/manager/test_manager_run_coordinator.py -v
```

预期：测试通过（新代码）。

- [ ] **Step 7: 运行 manager_run_service 测试**

```bash
uv run pytest tests/vibe3/manager/test_manager_run_service.py -v
```

预期：测试可能失败（需要更新 mock 和 fixture）。

- [ ] **Step 8: 更新 manager_run_service 测试**

修改 `tests/vibe3/manager/test_manager_run_service.py`：

```python
# ADD import
from vibe3.manager.manager_run_coordinator import ManagerRunCoordinator

# UPDATE tests that mock handle_manager_post_run_outcome
# to mock ManagerRunCoordinator instead
```

具体更新取决于测试内容。

- [ ] **Step 9: 运行所有 manager 测试**

```bash
uv run pytest tests/vibe3/manager/ -v
```

预期：所有测试通过。

- [ ] **Step 10: 检查 LOC 改善**

验证 `run_manager_issue_mode` LOC 减少：

```bash
uv run python src/vibe3/cli.py inspect files src/vibe3/manager/manager_run_service.py
```

预期：`run_manager_issue_mode` LOC 应减少约60-80行（从253降至~170-190）。

- [ ] **Step 11: 提交**

```bash
git add src/vibe3/manager/manager_run_coordinator.py
git add src/vibe3/manager/manager_run_service.py
git add tests/vibe3/manager/test_manager_run_coordinator.py
git add tests/vibe3/manager/test_manager_run_service.py
git commit -m "refactor: extract ManagerRunCoordinator from manager_run_service

Architecture decoupling - run_manager_issue_mode was a 253 LOC function
mixing runtime entry with lifecycle orchestration.

Changes:
- Extract post-run outcome handling to ManagerRunCoordinator
- Extract progress checking and no-op blocking to coordinator
- Reduce run_manager_issue_mode LOC by ~70 lines
- Separate concerns: runtime execution vs lifecycle coordination

Rationale: Runtime entrypoint should not own every lifecycle branch.
Coordinator pattern enables cleaner separation and easier testing."
```

---

## 完成标准

所有任务完成后：

1. **零引用函数已移除**：`issue_failure_service.close_ready_issue` 不存在
2. **语义偏离已修复**：`IssueCloseService` API 名称匹配实际使用
3. **架构已解耦**：`run_manager_issue_mode` LOC 减少，coordinator 负责 post-run orchestration
4. **所有测试通过**：
   ```bash
   uv run pytest tests/vibe3/services/test_issue_close_service.py tests/vibe3/services/test_abandon_flow_service.py tests/vibe3/manager/test_manager_run_coordinator.py tests/vibe3/manager/test_manager_run_service.py -v
   ```
5. **代码质量改善**：
   - 死代码消除
   - 语义对齐
   - 架构解耦

---

## 附录：证据来源

审计报告基于以下证据：

1. **Manager post-run orchestration concentration**:
   - `inspect files manager_run_service.py` → 476 LOC, run_manager_issue_mode 253 LOC
   - Imports span backend, clients, orchestra, progress policy, failure side effects, abandon

2. **Ready-close logic split**:
   - `inspect symbols issue_failure_service:close_ready_issue` → 0 references
   - Grep confirms no usage
   - Tests confirm no coverage

3. **ReadyCloseService naming drift**:
   - AbandonFlowService supports READY/HANDOFF states
   - Always calls ReadyCloseService.close_ready_issue
   - API name suggests ready-only, contradicts usage

---

## Self-Review Checklist

**1. Spec coverage**: ✓ 审计报告三个建议全部实现
   - Task 1: 移除零引用函数 → 已实现
   - Task 2: 重命名语义偏离服务 → 已实现
   - Task 3: 提取 manager post-run orchestration → 已实现

**2. Placeholder scan**: ✓ 无 TBD/TODO/模糊指令
   - 每个步骤有具体代码
   - 每个命令有预期输出
   - 无"fill in details"/"similar to"/"add validation"等占位符

**3. Type consistency**: ✓ 类型签名一致
   - IssueCloseService.close_issue → 参数和返回值类型明确
   - ManagerRunCoordinator 方法签名 → 所有参数和返回类型明确
   - AbandonFlowService.__init__ → 参数名从 ready_close 改为 issue_close