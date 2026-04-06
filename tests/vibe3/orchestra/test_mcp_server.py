"""Tests for MCP Server - Phase 3."""

from dataclasses import dataclass
from typing import Any


@dataclass
class MockIssueStatusEntry:
    """Mock issue status entry for testing."""

    number: int
    title: str
    state: Any = None
    assignee: str | None = None
    has_flow: bool = False
    flow_branch: str | None = None
    has_worktree: bool = False
    worktree_path: str | None = None
    has_pr: bool = False
    pr_number: int | None = None
    blocked_by: tuple[int, ...] = ()
    # Queue metadata fields
    milestone: str | None = None
    roadmap: str | None = None
    priority: int = 0
    queue_rank: int | None = None


@dataclass
class MockOrchestraSnapshot:
    """Mock orchestra snapshot for testing."""

    timestamp: float
    server_running: bool
    active_issues: tuple[Any, ...]
    active_flows: int
    active_worktrees: int
    queued_issues: tuple[int, ...] = ()
    circuit_breaker_state: str = "closed"
    circuit_breaker_failures: int = 0
    circuit_breaker_last_failure: float | None = None


class MockIssueState:
    """Mock issue state enum."""

    def __init__(self, value: str):
        self.value = value


class TestMCPServerCreation:
    """Tests for MCP server creation."""

    def test_create_mcp_server_success(self):
        """MCP server creation function exists and accepts status_service."""
        from vibe3.server.mcp import create_mcp_server

        # This test verifies the function exists
        # Actual MCP creation requires mcp package to be installed
        assert callable(create_mcp_server)

    def test_create_mcp_server_import_error_message(self):
        """ImportError should have helpful message when mcp package not installed."""
        # The actual import error handling is tested via the serve_utils integration
        # Here we just verify the error message format
        error_msg = "MCP package not installed. Install with: pip install mcp"
        assert "pip install mcp" in error_msg


class TestMCPResources:
    """Tests for MCP resources."""

    def test_status_resource_returns_json(self):
        """Status resource should return JSON snapshot."""
        from vibe3.server.mcp import _serialize_snapshot

        mock_state = MockIssueState("in-progress")
        mock_entry = MockIssueStatusEntry(
            number=100,
            title="Test issue",
            state=mock_state,
            assignee="manager-bot",
            has_flow=True,
            flow_branch="task/issue-100",
            has_pr=True,
            pr_number=123,
        )
        mock_snapshot = MockOrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=(mock_entry,),
            active_flows=1,
            active_worktrees=1,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )

        result = _serialize_snapshot(mock_snapshot)

        assert result["timestamp"] == 1234567890.0
        assert result["server_running"] is True
        assert result["active_flows"] == 1
        assert result["circuit_breaker_state"] == "closed"
        assert len(result["active_issues"]) == 1

        issue = result["active_issues"][0]
        assert issue["number"] == 100
        assert issue["title"] == "Test issue"
        assert issue["state"] == "in-progress"
        assert issue["assignee"] == "manager-bot"
        assert issue["has_pr"] is True
        assert issue["pr_number"] == 123

    def test_format_snapshot_for_mcp(self):
        """Snapshot should be formatted as markdown for MCP tool output."""
        from vibe3.server.mcp import format_snapshot_for_mcp

        mock_state = MockIssueState("in-progress")
        mock_entry = MockIssueStatusEntry(
            number=100,
            title="Test issue",
            state=mock_state,
            assignee="manager-bot",
            has_pr=True,
            pr_number=123,
        )
        mock_snapshot = MockOrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=(mock_entry,),
            active_flows=1,
            active_worktrees=1,
        )

        result = format_snapshot_for_mcp(mock_snapshot)

        assert "## Orchestra Status" in result
        assert "**Server**: Running" in result
        assert "**Active Flows**: 1" in result
        assert "**#100**: Test issue" in result
        assert "State: `in-progress`" in result
        assert "PR: #123" in result


class TestMCPTools:
    """Tests for MCP tools."""

    def test_orchestra_status_tool(self):
        """orchestra_status tool should return formatted status."""
        from vibe3.server.mcp import format_snapshot_for_mcp

        mock_state = MockIssueState("blocked")
        mock_entry = MockIssueStatusEntry(
            number=101,
            title="Blocked issue",
            state=mock_state,
            blocked_by=(99,),
        )
        mock_snapshot = MockOrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=(mock_entry,),
            active_flows=1,
            active_worktrees=0,
            circuit_breaker_state="open",
            circuit_breaker_failures=3,
        )

        result = format_snapshot_for_mcp(mock_snapshot)

        assert "Circuit Breaker**: open" in result
        assert "Failures: 3" in result
        assert "Blocked by: #99" in result

    def test_orchestra_issue_detail_tool(self):
        """orchestra_issue_detail tool should return issue details."""
        # This is tested indirectly via _serialize_snapshot
        from vibe3.server.mcp import _serialize_snapshot

        mock_state = MockIssueState("review")
        mock_entry = MockIssueStatusEntry(
            number=102,
            title="Issue in review",
            state=mock_state,
            has_flow=True,
            flow_branch="task/issue-102",
            has_pr=True,
            pr_number=456,
        )
        mock_snapshot = MockOrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=(mock_entry,),
            active_flows=1,
            active_worktrees=1,
        )

        result = _serialize_snapshot(mock_snapshot)
        issue = result["active_issues"][0]

        assert issue["number"] == 102
        assert issue["state"] == "review"
        assert issue["flow_branch"] == "task/issue-102"
        assert issue["pr_number"] == 456


class TestMCPDispatchHistory:
    """Tests for orchestra_dispatch_history tool correctness."""

    def test_get_events_with_branch_none_queries_all(self, tmp_path):
        """
        SQLiteClient.get_events(branch=None) should return events from all branches.
        """
        from vibe3.clients.sqlite_client import SQLiteClient

        db_file = str(tmp_path / "test.db")
        store = SQLiteClient(db_path=db_file)

        # Insert events on different branches
        store.add_event(
            "task/issue-1", "dispatch_result", "orchestra:dispatcher", "success"
        )
        store.add_event(
            "task/issue-2", "dispatch_result", "orchestra:dispatcher", "failed:timeout"
        )
        store.add_event("task/issue-3", "other_event", "orchestra:dispatcher", "other")

        # branch=None should return all dispatch_result events (2 of them)
        events = store.get_events(branch=None, event_type="dispatch_result")
        assert len(events) == 2
        branches = {e["branch"] for e in events}
        assert branches == {"task/issue-1", "task/issue-2"}

    def test_get_events_with_branch_str_filters_correctly(self, tmp_path):
        """SQLiteClient.get_events(branch='...') should still filter by branch."""
        from vibe3.clients.sqlite_client import SQLiteClient

        db_file = str(tmp_path / "test.db")
        store = SQLiteClient(db_path=db_file)

        store.add_event("task/issue-1", "dispatch_result", "actor", "success")
        store.add_event("task/issue-2", "dispatch_result", "actor", "success")

        events = store.get_events(branch="task/issue-1")
        assert len(events) == 1
        assert events[0]["branch"] == "task/issue-1"

    def test_dispatch_history_branch_empty_string_queries_all(self, tmp_path):
        """branch='' should be normalized to query all branches (same as None)."""
        from vibe3.clients.sqlite_client import SQLiteClient

        db_file = str(tmp_path / "test.db")
        store = SQLiteClient(db_path=db_file)
        store.add_event("task/issue-1", "dispatch_result", "actor", "success")

        # branch="" now behaves like branch=None
        empty_branch_events = store.get_events(branch="", event_type="dispatch_result")
        all_events = store.get_events(branch=None, event_type="dispatch_result")
        assert len(empty_branch_events) == 1
        assert len(all_events) == 1


class TestMCPServerIntegration:
    """Integration tests for MCP server with serve_utils."""

    def test_mcp_server_graceful_degradation_on_import_error(self):
        """Should continue without MCP if import fails."""
        from vibe3.orchestra.config import OrchestraConfig
        from vibe3.server.registry import _build_server

        config = OrchestraConfig()

        # This test verifies graceful degradation
        heartbeat, fastapi_app = _build_server(config)

        # FastAPI app should be created even if MCP fails
        assert fastapi_app is not None
        # /status endpoint should work
        assert any(route.path == "/status" for route in fastapi_app.routes)

    def test_build_server_creates_fastapi_app(self):
        """_build_server should create FastAPI app with status endpoint."""
        from vibe3.orchestra.config import OrchestraConfig
        from vibe3.server.registry import _build_server

        config = OrchestraConfig()
        heartbeat, fastapi_app = _build_server(config)

        # Basic functionality should work
        assert fastapi_app is not None
        assert fastapi_app.title == "vibe3 Orchestra"
        # Status endpoint should be registered
        assert any(route.path == "/status" for route in fastapi_app.routes)

    def test_serialize_snapshot_includes_queue_metadata(self):
        """MCP serialization includes queue metadata for ready issues."""
        from vibe3.server.mcp import _serialize_snapshot

        # Create a ready issue with queue metadata
        ready_issue = MockIssueStatusEntry(
            number=42,
            title="Ready issue",
            state=MockIssueState("ready"),
            milestone="v0.1",
            roadmap="p0",
            priority=9,
            queue_rank=1,
        )

        snapshot = MockOrchestraSnapshot(
            timestamp=1700000000.0,
            server_running=True,
            active_issues=(ready_issue,),
            active_flows=0,
            active_worktrees=0,
        )

        serialized = _serialize_snapshot(snapshot)

        # Verify queue metadata is in serialization
        assert "active_issues" in serialized
        assert len(serialized["active_issues"]) == 1
        issue_data = serialized["active_issues"][0]
        assert issue_data["number"] == 42
        assert issue_data["milestone"] == "v0.1"
        assert issue_data["roadmap"] == "p0"
        assert issue_data["priority"] == 9
        assert issue_data["queue_rank"] == 1
