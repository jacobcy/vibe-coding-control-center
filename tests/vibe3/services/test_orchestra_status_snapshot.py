"""Tests for OrchestraStatusService snapshot boundary behavior."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.orchestra.failed_gate import GateResult
from vibe3.services.orchestra.status import OrchestraStatusService


class TestSnapshotIssuePoolBoundary:
    """Tests that snapshot correctly respects assignee issue pool boundary."""

    def _make_service(self, github_mock: MagicMock) -> OrchestraStatusService:
        config = OrchestraConfig(
            manager_usernames=["manager-bot"],
            repo="test/repo",
        )
        orchestrator = MagicMock()
        orchestrator.get_flow_for_issue.return_value = None
        orchestrator.get_active_flow_count.return_value = 0

        return OrchestraStatusService(
            config=config,
            github=github_mock,
            orchestrator=orchestrator,
        )

    def test_snapshot_excludes_supervisor_issues(self):
        """Supervisor issues must not appear in the assignee issue snapshot."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 100,
                "title": "Assignee issue",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "state/ready"}],
                "milestone": None,
                "body": "",
            },
            {
                "number": 200,
                "title": "Supervisor issue",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
                "milestone": None,
                "body": "",
            },
        ]

        service = self._make_service(github)
        snapshot = service.snapshot()

        numbers = [entry.number for entry in snapshot.active_issues]
        assert 100 in numbers
        assert 200 not in numbers

    def test_snapshot_includes_only_assignee_issues(self):
        """Snapshot should only contain issues from assignee pool."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 101,
                "title": "Feature A",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "state/ready"}, {"name": "vibe-task"}],
                "milestone": None,
                "body": "",
            },
        ]

        service = self._make_service(github)
        snapshot = service.snapshot()

        assert len(snapshot.active_issues) == 1
        assert snapshot.active_issues[0].number == 101

    def test_snapshot_empty_when_only_supervisor_issues(self):
        """Snapshot is empty when no assignee issues exist."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 300,
                "title": "Cleanup task",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "supervisor"}],
                "milestone": None,
                "body": "",
            },
        ]

        service = self._make_service(github)
        snapshot = service.snapshot()

        assert len(snapshot.active_issues) == 0

    def test_snapshot_uses_first_non_blank_assignee_and_shared_queue_ordering(self):
        """Snapshot should normalize assignee and preserve queue metadata ordering."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 401,
                "title": "Higher priority ready issue",
                "assignees": [{"login": "   "}, {"login": "manager-bot"}],
                "labels": [{"name": "state/ready"}, {"name": "priority/9"}],
                "milestone": {"title": "v1"},
                "body": "",
            },
            {
                "number": 402,
                "title": "Lower priority ready issue",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "state/ready"}, {"name": "priority/1"}],
                "milestone": {"title": "v1"},
                "body": "",
            },
        ]

        service = self._make_service(github)
        service._label_service = MagicMock()
        service._label_service.get_state.return_value = IssueState.READY
        snapshot = service.snapshot()

        assert [entry.number for entry in snapshot.active_issues] == [401, 402]
        assert snapshot.active_issues[0].assignee == "manager-bot"
        assert snapshot.active_issues[0].queue_rank == 1
        assert snapshot.active_issues[1].queue_rank == 2

    def test_snapshot_handles_failed_gate_without_issue_number(self):
        """Failed gate snapshot should not require a nonexistent issue number."""
        github = MagicMock()
        github.list_issues.return_value = []
        failed_gate = MagicMock()
        failed_gate.check.return_value = GateResult(
            blocked=True,
            reason="API/Exec error threshold: 3 recent errors",
            blocked_ticks=2,
        )

        service = self._make_service(github)
        service._failed_gate = failed_gate

        snapshot = service.snapshot()

        assert snapshot.dispatch_blocked is True
        assert snapshot.blocked_issue_number is None
        assert (
            snapshot.blocked_issue_reason == "API/Exec error threshold: 3 recent errors"
        )

    def test_snapshot_batches_pr_lookup_without_per_issue_branch_fallback(self):
        """snapshot should batch PR lookup via PRService instead of
        per-issue get_pr_for_issue."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 501,
                "title": "Issue with PR",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "state/in-progress"}],
                "milestone": None,
                "body": "",
            },
            {
                "number": 502,
                "title": "Issue without PR",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "state/in-progress"}],
                "milestone": None,
                "body": "",
            },
        ]

        config = OrchestraConfig(
            manager_usernames=["manager-bot"],
            repo="test/repo",
        )
        orchestrator = MagicMock()
        orchestrator.get_active_flow_count.return_value = 2
        orchestrator.get_flow_for_issue.side_effect = lambda n: (
            {
                "branch": f"task/issue-{n}",
                "pr_number": None,
            }
            if n in (501, 502)
            else None
        )
        orchestrator.get_pr_for_issue.side_effect = AssertionError(
            "snapshot should not call per-issue PR fallback"
        )

        mock_pr_service = MagicMock()
        mock_pr_service.refresh_recent_pr_cache.return_value = {
            "task/issue-501": MagicMock(number=9001),
        }

        with patch(
            "vibe3.services.orchestra.status.PRService",
            return_value=mock_pr_service,
        ):
            service = OrchestraStatusService(
                config=config,
                github=github,
                orchestrator=orchestrator,
            )
            snapshot = service.snapshot()

        mock_pr_service.refresh_recent_pr_cache.assert_called_once_with(
            sync_context_cache=False
        )
        orchestrator.get_pr_for_issue.assert_not_called()
        assert len(snapshot.active_issues) == 2
        issue_501 = next(e for e in snapshot.active_issues if e.number == 501)
        issue_502 = next(e for e in snapshot.active_issues if e.number == 502)
        assert issue_501.pr_number == 9001
        assert issue_502.pr_number is None

    def test_snapshot_includes_log_path_field(self):
        """Snapshot should include log_path field with non-empty absolute path."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 600,
                "title": "Test issue",
                "assignees": [{"login": "manager-bot"}],
                "labels": [{"name": "state/ready"}],
                "milestone": None,
                "body": "",
            },
        ]

        service = self._make_service(github)
        snapshot = service.snapshot()

        # log_path should be a non-empty string
        assert hasattr(snapshot, "log_path")
        assert isinstance(snapshot.log_path, str)
        assert len(snapshot.log_path) > 0
        # Should be an absolute path containing expected components
        assert "temp" in snapshot.log_path
        assert "logs" in snapshot.log_path
        assert "events.log" in snapshot.log_path
