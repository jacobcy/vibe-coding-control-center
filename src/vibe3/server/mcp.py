"""MCP Server for Orchestra - exposes orchestra state to external AI agents."""

import json
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from vibe3.orchestra.services.status_service import (
        OrchestraSnapshot,
        OrchestraStatusService,
    )


def _serialize_snapshot(snapshot: "OrchestraSnapshot") -> dict:
    """Convert OrchestraSnapshot to JSON-serializable dict."""
    return {
        "timestamp": snapshot.timestamp,
        "server_running": snapshot.server_running,
        "active_flows": snapshot.active_flows,
        "active_worktrees": snapshot.active_worktrees,
        "circuit_breaker_state": snapshot.circuit_breaker_state,
        "circuit_breaker_failures": snapshot.circuit_breaker_failures,
        "circuit_breaker_last_failure": snapshot.circuit_breaker_last_failure,
        "active_issues": [
            {
                "number": entry.number,
                "title": entry.title,
                "state": entry.state.value if entry.state else None,
                "assignee": entry.assignee,
                "has_flow": entry.has_flow,
                "flow_branch": entry.flow_branch,
                "has_worktree": entry.has_worktree,
                "worktree_path": entry.worktree_path,
                "has_pr": entry.has_pr,
                "pr_number": entry.pr_number,
                "blocked_by": list(entry.blocked_by),
            }
            for entry in snapshot.active_issues
        ],
    }


def format_snapshot_for_mcp(snapshot: "OrchestraSnapshot") -> str:
    """Format snapshot for MCP tool output."""
    lines = [
        f"## Orchestra Status (timestamp: {snapshot.timestamp:.0f})",
        "",
        f"- **Server**: {'Running' if snapshot.server_running else 'Stopped'}",
        f"- **Active Flows**: {snapshot.active_flows}",
        f"- **Active Worktrees**: {snapshot.active_worktrees}",
        f"- **Circuit Breaker**: {snapshot.circuit_breaker_state}",
        f"  - Failures: {snapshot.circuit_breaker_failures}",
        "",
        "### Active Issues",
        "",
    ]

    for entry in snapshot.active_issues:
        state_str = entry.state.value if entry.state else "unknown"
        lines.append(f"- **#{entry.number}**: {entry.title}")
        lines.append(f"  - State: `{state_str}`")
        if entry.assignee:
            lines.append(f"  - Assignee: {entry.assignee}")
        if entry.has_pr and entry.pr_number:
            lines.append(f"  - PR: #{entry.pr_number}")
        if entry.blocked_by:
            blocked_str = ", ".join(f"#{n}" for n in entry.blocked_by)
            lines.append(f"  - Blocked by: {blocked_str}")
        lines.append("")

    return "\n".join(lines)


def create_mcp_server(
    status_service: "OrchestraStatusService",
) -> "FastMCP":
    """Create MCP server for Orchestra.

    Args:
        status_service: OrchestraStatusService instance

    Returns:
        FastMCP server instance

    Raises:
        ImportError: If mcp package is not installed
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise ImportError(
            "MCP package not installed. Install with: pip install mcp"
        ) from exc

    mcp = FastMCP("orchestra")

    @mcp.resource("orchestra://status")
    def get_status_resource() -> str:
        """Get current orchestra status as JSON."""
        snapshot = status_service.snapshot()
        return json.dumps(_serialize_snapshot(snapshot), indent=2)

    @mcp.resource("orchestra://issues")
    def get_issues_resource() -> str:
        """Get list of managed issues with their states."""
        snapshot = status_service.snapshot()
        issues_data = [
            {
                "number": entry.number,
                "title": entry.title,
                "state": entry.state.value if entry.state else None,
                "assignee": entry.assignee,
                "has_flow": entry.has_flow,
                "has_pr": entry.has_pr,
                "pr_number": entry.pr_number,
                "blocked_by": list(entry.blocked_by),
            }
            for entry in snapshot.active_issues
        ]
        return json.dumps(issues_data, indent=2)

    @mcp.resource("orchestra://circuit-breaker")
    def get_circuit_breaker_resource() -> str:
        """Get circuit breaker state."""
        snapshot = snapshot = status_service.snapshot()
        cb_data = {
            "state": snapshot.circuit_breaker_state,
            "failures": snapshot.circuit_breaker_failures,
            "last_failure": snapshot.circuit_breaker_last_failure,
        }
        return json.dumps(cb_data, indent=2)

    @mcp.tool()
    def orchestra_status() -> str:
        """Get current orchestra system status.

        Returns a formatted summary of the orchestra system including:
        - Server status
        - Active flows and worktrees
        - Circuit breaker state
        - Active issues with their states
        """
        snapshot = status_service.snapshot()
        return format_snapshot_for_mcp(snapshot)

    @mcp.tool()
    def orchestra_issue_detail(issue_number: int) -> str:
        """Get detailed information about a specific issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            JSON-formatted issue details including flow, worktree, and PR status
        """
        snapshot = status_service.snapshot()
        for entry in snapshot.active_issues:
            if entry.number == issue_number:
                return json.dumps(
                    {
                        "number": entry.number,
                        "title": entry.title,
                        "state": entry.state.value if entry.state else None,
                        "assignee": entry.assignee,
                        "has_flow": entry.has_flow,
                        "flow_branch": entry.flow_branch,
                        "has_worktree": entry.has_worktree,
                        "worktree_path": entry.worktree_path,
                        "has_pr": entry.has_pr,
                        "pr_number": entry.pr_number,
                        "blocked_by": list(entry.blocked_by),
                    },
                    indent=2,
                )
        return json.dumps(
            {"error": f"Issue #{issue_number} not in active issues"},
            indent=2,
        )

    @mcp.tool()
    def orchestra_dispatch_history(limit: int = 10) -> str:
        """View recent dispatch execution history.

        Args:
            limit: Maximum number of events to return (default: 10)

        Returns:
            JSON-formatted list of recent dispatch events from flow history
        """
        try:
            from vibe3.clients import SQLiteClient

            safe_limit = max(1, min(limit, 100))
            store = SQLiteClient()
            events = store.get_events(
                branch=None,  # None = query all branches
                event_type="dispatch_result",
                limit=safe_limit,
            )

            formatted_events = [
                {
                    "branch": event.get("branch"),
                    "created_at": event.get("created_at"),
                    "detail": event.get("detail"),
                    "refs": event.get("refs"),
                }
                for event in events
            ]
            return json.dumps(formatted_events, indent=2)
        except Exception as exc:
            logger.bind(domain="orchestra").error(
                f"Failed to get dispatch history: {exc}"
            )
            return json.dumps(
                {"error": f"Failed to get dispatch history: {exc}"},
                indent=2,
            )

    log = logger.bind(domain="orchestra")
    log.info("MCP server created with 3 resources and 3 tools")
    return mcp
