"""End-to-end integration tests for health check flow."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.check_service import CheckService


def test_closed_issue_flow_gets_aborted_e2e(tmp_path: Path) -> None:
    """Closed issue should result in aborted flow status."""
    # Setup: create fresh database and store
    db_path = tmp_path / "handoff.db"
    store = SQLiteClient(db_path=str(db_path))
    branch = "task/issue-789"

    # Setup: create flow in active state with task issue link
    store.update_flow_state(branch, flow_slug="test_flow", flow_status="active")
    store.add_issue_link(branch, 789, "task")

    # Verify initial state
    flow_data = store.get_flow_state(branch)
    assert flow_data is not None
    assert flow_data["flow_status"] == "active"

    # Simulate: user closes issue on GitHub
    # Run: CheckService discovers closed issue
    service = CheckService(store=store)
    mock_github = MagicMock(spec=GitHubClient)
    mock_github.view_issue.return_value = {
        "number": 789,
        "state": "CLOSED",
        "labels": [],
    }
    mock_github.list_all_prs.return_value = []
    service.github_client = mock_github
    service._initialize_pr_cache()

    result = service.verify_branch(branch)

    # Verify: flow marked as aborted
    assert result.is_valid is True  # Valid because auto-fixed
    assert result.branch == branch

    # Verify database state directly
    with sqlite3.connect(str(db_path)) as conn:
        row = conn.execute(
            "SELECT flow_status FROM flow_state WHERE branch = ?", (branch,)
        ).fetchone()
        assert row is not None
        assert row[0] == "aborted"

    # Verify event was recorded
    events = store.get_events(branch)
    assert any("flow_auto_aborted" in str(e) for e in events)
