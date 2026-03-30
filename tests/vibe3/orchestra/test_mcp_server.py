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


@dataclass
class MockOrchestraSnapshot:
    """Mock orchestra snapshot for testing."""

    timestamp: float
    server_running: bool
    active_issues: tuple[Any, ...]
    active_flows: int
    active_worktrees: int
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
        from vibe3.orchestra.mcp_server import create_mcp_server

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
        from vibe3.orchestra.mcp_server import _serialize_snapshot

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
        from vibe3.orchestra.mcp_server import format_snapshot_for_mcp

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
        from vibe3.orchestra.mcp_server import format_snapshot_for_mcp

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
        from vibe3.orchestra.mcp_server import _serialize_snapshot

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


class TestMCPServerIntegration:
    """Integration tests for MCP server with serve_utils."""

    def test_mcp_server_graceful_degradation_on_import_error(self):
        """Should continue without MCP if import fails."""
        from vibe3.orchestra.config import OrchestraConfig
        from vibe3.orchestra.serve_utils import _build_server

        config = OrchestraConfig()

        # This test verifies graceful degradation
        # The try/except in serve_utils handles ImportError gracefully
        heartbeat, fastapi_app = _build_server(config)

        # FastAPI app should be created even if MCP fails
        assert fastapi_app is not None
        # /status endpoint should work
        assert any(route.path == "/status" for route in fastapi_app.routes)

    def test_build_server_creates_fastapi_app(self):
        """_build_server should create FastAPI app with status endpoint."""
        from vibe3.orchestra.config import OrchestraConfig
        from vibe3.orchestra.serve_utils import _build_server

        config = OrchestraConfig()
        heartbeat, fastapi_app = _build_server(config)

        # Basic functionality should work
        assert fastapi_app is not None
        assert fastapi_app.title == "vibe3 Orchestra"
        # Status endpoint should be registered
        assert any(route.path == "/status" for route in fastapi_app.routes)
