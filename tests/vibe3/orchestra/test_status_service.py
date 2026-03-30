"""Tests for OrchestraStatusService."""

from unittest.mock import patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.services.status_service import (
    IssueStatusEntry,
    OrchestraSnapshot,
    OrchestraStatusService,
)
from vibe3.ui.orchestra_ui import _format_snapshot


def _make_config() -> OrchestraConfig:
    return OrchestraConfig(
        enabled=True,
        polling_interval=900,
        repo="test/repo",
        manager_usernames=["vibe-manager-agent"],
    )


class TestOrchestraStatusService:
    def test_snapshot_empty(self) -> None:
        """Snapshot with no issues returns empty list."""
        config = _make_config()
        service = OrchestraStatusService(config)

        with (
            patch.object(service._github, "list_issues", return_value=[]) as mock_list,
            patch.object(service._git, "list_worktrees", return_value=[]),
        ):
            snapshot = service.snapshot()

        assert snapshot.server_running is True
        assert snapshot.active_issues == ()
        assert snapshot.active_flows == 0
        assert snapshot.active_worktrees == 0
        mock_list.assert_called_once()

    def test_snapshot_with_issue(self) -> None:
        """Snapshot includes issue with flow and worktree."""
        config = _make_config()
        service = OrchestraStatusService(config)

        mock_issue = {
            "number": 42,
            "title": "Test issue",
            "assignees": [{"login": "vibe-manager-agent"}],
        }
        mock_flow = {"branch": "task/issue-42"}
        mock_worktrees = [
            ("/repo", "refs/heads/main"),
            ("/repo/.worktrees/issue-42", "refs/heads/task/issue-42"),
        ]

        with (
            patch.object(service._github, "list_issues", return_value=[mock_issue]),
            patch.object(
                service._label_service, "get_state", return_value=IssueState.IN_PROGRESS
            ),
            patch.object(
                service._orchestrator, "get_flow_for_issue", return_value=mock_flow
            ),
            patch.object(service._orchestrator, "get_pr_for_issue", return_value=None),
            patch.object(service._git, "list_worktrees", return_value=mock_worktrees),
        ):
            snapshot = service.snapshot()

        assert len(snapshot.active_issues) == 1
        entry = snapshot.active_issues[0]
        assert entry.number == 42
        assert entry.title == "Test issue"
        assert entry.state == IssueState.IN_PROGRESS
        assert entry.has_flow is True
        assert entry.flow_branch == "task/issue-42"
        assert snapshot.active_worktrees == 2

    def test_snapshot_multiple_managers(self) -> None:
        """Snapshot aggregates issues from multiple manager usernames."""
        config = OrchestraConfig(
            enabled=True,
            polling_interval=900,
            repo="test/repo",
            manager_usernames=["manager-1", "manager-2"],
        )
        service = OrchestraStatusService(config)

        with (
            patch.object(
                service._github,
                "list_issues",
                side_effect=[
                    [{"number": 1, "title": "Issue 1", "assignees": []}],
                    [{"number": 2, "title": "Issue 2", "assignees": []}],
                ],
            ),
            patch.object(service._label_service, "get_state", return_value=None),
            patch.object(
                service._orchestrator, "get_flow_for_issue", return_value=None
            ),
            patch.object(service._git, "list_worktrees", return_value=[]),
        ):
            snapshot = service.snapshot()

        assert len(snapshot.active_issues) == 2

    def test_format_snapshot(self) -> None:
        """_format_snapshot produces readable output."""
        entry = IssueStatusEntry(
            number=42,
            title="Test issue title",
            state=IssueState.IN_PROGRESS,
            assignee="vibe-manager-agent",
            has_flow=True,
            flow_branch="task/issue-42",
            has_worktree=True,
            worktree_path="/repo/.worktrees/issue-42",
            has_pr=False,
            pr_number=None,
        )
        snapshot = OrchestraSnapshot(
            timestamp=1700000000.0,
            server_running=True,
            active_issues=(entry,),
            active_flows=1,
            active_worktrees=1,
        )

        output = _format_snapshot(snapshot)

        assert "Orchestra Status" in output
        assert "#42" in output
        assert "state/in-progress" in output
        assert "flow=task/issue-42" in output
        assert "Flows: 1 active" in output


class TestIssueStatusEntry:
    def test_entry_is_frozen(self) -> None:
        """IssueStatusEntry is immutable (frozen dataclass)."""
        entry = IssueStatusEntry(
            number=1,
            title="test",
            state=IssueState.READY,
            assignee=None,
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.number = 2  # type: ignore[misc]


class TestOrchestraSnapshot:
    def test_snapshot_is_frozen(self) -> None:
        """OrchestraSnapshot is immutable (frozen dataclass)."""
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            snapshot.server_running = False  # type: ignore[misc]
