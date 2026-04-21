"""Tests for OrchestraStatusService snapshot boundary behavior."""

from unittest.mock import MagicMock

from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.orchestra_status_service import OrchestraStatusService


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
