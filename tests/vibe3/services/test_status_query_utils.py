"""Unit tests for StatusQueryService utility functions."""

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import (
    StatusQueryService,
    is_auto_task_branch,
    is_canonical_task_branch,
    issue_priority,
)


class TestIssuePriority:
    """Tests for issue priority sorting."""

    def test_in_progress_has_highest_priority(self) -> None:
        """IN_PROGRESS should sort before all other states."""
        assert issue_priority(IssueState.IN_PROGRESS) < issue_priority(IssueState.READY)
        assert issue_priority(IssueState.IN_PROGRESS) < issue_priority(
            IssueState.BLOCKED
        )

    def test_ready_before_blocked(self) -> None:
        """READY should sort before BLOCKED."""
        assert issue_priority(IssueState.READY) < issue_priority(IssueState.BLOCKED)

    def test_blocked_has_lower_priority(self) -> None:
        """BLOCKED should have lower priority than IN_PROGRESS and READY."""
        assert issue_priority(IssueState.BLOCKED) > issue_priority(IssueState.READY)
        assert issue_priority(IssueState.BLOCKED) > issue_priority(
            IssueState.IN_PROGRESS
        )


class TestBranchClassification:
    """Tests for branch name classification helpers."""

    def test_is_auto_task_branch_recognizes_pattern(self) -> None:
        """Should recognize task/issue-N pattern."""
        assert is_auto_task_branch("task/issue-278") is True
        assert is_auto_task_branch("task/issue-320") is True
        assert is_auto_task_branch("dev/feature") is False
        assert is_auto_task_branch("main") is False

    def test_is_canonical_task_branch_matches_issue_number(self) -> None:
        """Should match when branch exactly matches task/issue-N."""
        assert is_canonical_task_branch("task/issue-278", 278) is True
        assert is_canonical_task_branch("task/issue-278", 320) is False
        assert is_canonical_task_branch("dev/issue-278", 278) is False
        assert is_canonical_task_branch("task/issue-278", None) is False


class TestRemoteField:
    """Tests for remote field calculation in fetch_orchestrated_issues."""

    def _make_mock_service(self) -> StatusQueryService:
        """Create a StatusQueryService with mocked dependencies."""
        github_mock = MagicMock()
        github_mock.list_issues.return_value = []
        git_mock = MagicMock()
        store_mock = MagicMock()

        return StatusQueryService(
            github_client=github_mock,
            git_client=git_mock,
            store=store_mock,
        )

    def test_remote_true_when_claimed_by_manager_without_flow(self) -> None:
        """state ≠ ready + manager assignee + no flow → remote=True."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 101,
                "title": "Remote task",
                "labels": [{"name": "state/claimed"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is True
        assert result[0]["assignee"] == "manager-bot"
        assert result[0]["state"] == IssueState.CLAIMED

    def test_remote_false_when_non_manager_assignee(self) -> None:
        """state ≠ ready + non-manager assignee → remote=False."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 102,
                "title": "Human task",
                "labels": [{"name": "state/claimed"}],
                "assignees": [{"login": "jacobcy"}],
                "milestone": None,
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is False
        assert result[0]["assignee"] == "jacobcy"

    def test_remote_false_when_ready_state(self) -> None:
        """state = ready + manager assignee + no flow → remote=False."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 103,
                "title": "Ready task",
                "labels": [{"name": "state/ready"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is False
        assert result[0]["state"] == IssueState.READY

    def test_remote_false_when_has_flow(self) -> None:
        """state ≠ ready + manager assignee + has flow → remote=False."""
        from types import SimpleNamespace

        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 104,
                "title": "Active task",
                "labels": [{"name": "state/claimed"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            }
        ]

        flow = SimpleNamespace(
            branch="task/issue-104",
            flow_status="active",
            task_issue_number=104,
        )

        result = service.fetch_orchestrated_issues(
            flows=[flow],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is False
        assert result[0]["flow"] is not None

    def test_remote_false_when_manager_usernames_none(self) -> None:
        """manager_usernames=None → remote=False."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 105,
                "title": "Unconfigured manager",
                "labels": [{"name": "state/claimed"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=None,
        )

        assert len(result) == 1
        assert result[0]["remote"] is False

    def test_blocked_state_remote_when_manager_assigned_no_flow(self) -> None:
        """BLOCKED state should be remote when manager-assigned without flow."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 106,
                "title": "Blocked task",
                "labels": [{"name": "state/blocked"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is True
        assert result[0]["state"] == IssueState.BLOCKED

    def test_blocked_remote_parses_reason_from_body(self) -> None:
        """Remote BLOCKED issues should parse blocked_reason from issue body."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 107,
                "title": "Remote blocked task",
                "labels": [{"name": "state/blocked"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
                "body": """<!-- vibe3-flow-state-start -->
## Managed Section

- **State**: blocked
- **Blocked by**: #123, #456
- **Blocked reason**: Waiting for external dependency
<!-- vibe3-flow-state-end -->
""",
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is True
        assert result[0]["state"] == IssueState.BLOCKED
        assert result[0]["blocked_reason"] == "Waiting for external dependency"
        assert result[0]["blocked_by"] == (123, 456)

    def test_keeps_no_state_items_with_dispatch_exclusion_reasons(self) -> None:
        """Issues without state/* should still be returned for dashboard
        classification."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 201,
                "title": "Missing state epic",
                "labels": [{"name": "roadmap/epic"}],
                "assignees": [],
                "milestone": None,
            },
            {
                "number": 202,
                "title": "Ready queue item",
                "labels": [{"name": "state/ready"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            },
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert [item["number"] for item in result] == [202, 201]
        assert result[0]["dispatch_exclusion_codes"] == []
        assert result[1]["state"] is None
        assert result[1]["dispatch_exclusion_codes"] == [
            "missing_state_label",
            "roadmap_epic",
            "missing_manager_assignee",
        ]

    def test_handoff_state_remote(self) -> None:
        """HANDOFF state with manager assignee and no flow should be remote."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 107,
                "title": "Handoff task",
                "labels": [{"name": "state/handoff"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is True
        assert result[0]["state"] == IssueState.HANDOFF

    def test_merge_ready_state_remote(self) -> None:
        """MERGE_READY state with manager assignee and no flow should be remote."""
        service = self._make_mock_service()
        service.github.list_issues.return_value = [
            {
                "number": 108,
                "title": "Merge ready task",
                "labels": [{"name": "state/merge-ready"}],
                "assignees": [{"login": "manager-bot"}],
                "milestone": None,
            }
        ]

        result = service.fetch_orchestrated_issues(
            flows=[],
            queued_set=set(),
            manager_usernames=["manager-bot"],
        )

        assert len(result) == 1
        assert result[0]["remote"] is True
        assert result[0]["state"] == IssueState.MERGE_READY
