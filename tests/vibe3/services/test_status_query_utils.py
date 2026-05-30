"""Unit tests for StatusQueryService utility functions."""

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import (
    StatusQueryService,
    _parse_dependencies_from_body,
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

    def test_blocked_state_not_remote(self) -> None:
        """BLOCKED state should not be marked as remote."""
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
        assert result[0]["remote"] is False
        assert result[0]["state"] == IssueState.BLOCKED

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


class TestParseDependenciesFromBody:
    """Tests for _parse_dependencies_from_body function."""

    def test_standard_dependencies_section(self) -> None:
        """Should parse standard ## Dependencies section."""
        body = """## Summary
This is an epic.

## Dependencies
- Blocked by #123 (need API)
- Blocked by #456 (need DB)

## Notes
Some notes.
"""
        result = _parse_dependencies_from_body(body)
        assert result == [123, 456]

    def test_mixed_format(self) -> None:
        """Should handle various formats within dependencies section."""
        body = """## Dependencies
- Blocked by #100
- #200 (another format)
- Blocked by #300 (with description)
"""
        result = _parse_dependencies_from_body(body)
        # Should find all issue numbers
        assert 100 in result
        assert 200 in result
        assert 300 in result

    def test_no_dependencies_section(self) -> None:
        """Should return empty list if no ## Dependencies section."""
        body = """## Summary
This is an epic.

## Notes
Some notes.
"""
        result = _parse_dependencies_from_body(body)
        assert result == []

    def test_empty_dependencies_section(self) -> None:
        """Should return empty list if dependencies section is empty."""
        body = """## Dependencies

## Notes
"""
        result = _parse_dependencies_from_body(body)
        assert result == []

    def test_ignores_references_outside_section(self) -> None:
        """Should only parse issue numbers inside ## Dependencies section."""
        body = """## Summary
This references #999.

## Dependencies
- Blocked by #123

## Notes
Also references #888.
"""
        result = _parse_dependencies_from_body(body)
        assert result == [123]
        assert 999 not in result
        assert 888 not in result

    def test_empty_body(self) -> None:
        """Should handle empty body."""
        result = _parse_dependencies_from_body("")
        assert result == []

    def test_none_body(self) -> None:
        """Should handle None body."""
        result = _parse_dependencies_from_body(None)  # type: ignore
        assert result == []

    def test_deduplication(self) -> None:
        """Should deduplicate issue numbers."""
        body = """## Dependencies
- Blocked by #123
- Blocked by #123 (duplicate)
- Blocked by #456
"""
        result = _parse_dependencies_from_body(body)
        assert result == [123, 456]

    def test_section_ended_by_next_header(self) -> None:
        """Should stop parsing at next section header."""
        body = """## Dependencies
- Blocked by #100

## Notes
- Blocked by #200
"""
        result = _parse_dependencies_from_body(body)
        assert result == [100]
        assert 200 not in result


class TestCheckEpicDependencyStatus:
    """Tests for check_epic_dependency_status method."""

    def _make_mock_service(self) -> StatusQueryService:
        """Create a StatusQueryService with mocked dependencies."""
        github_mock = MagicMock()
        git_mock = MagicMock()
        store_mock = MagicMock()
        return StatusQueryService(
            github_client=github_mock,
            git_client=git_mock,
            store=store_mock,
        )

    def test_all_dependencies_closed(self) -> None:
        """All dependencies CLOSED -> completed == total, is_ready == True."""
        service = self._make_mock_service()
        service.github.get_issue_body.return_value = """## Dependencies
- Blocked by #100
- Blocked by #200
"""
        service.github.view_issue.side_effect = [
            {"number": 100, "state": "CLOSED"},
            {"number": 200, "state": "CLOSED"},
        ]

        result = service.check_epic_dependency_status(1)

        assert result["total"] == 2
        assert result["completed"] == 2
        assert result["is_ready"] is True
        assert "✓" in result["summary_text"]

    def test_some_dependencies_open(self) -> None:
        """Some OPEN dependencies -> completed < total, is_ready == False."""
        service = self._make_mock_service()
        service.github.get_issue_body.return_value = """## Dependencies
- Blocked by #100
- Blocked by #200
"""
        service.github.view_issue.side_effect = [
            {"number": 100, "state": "CLOSED"},
            {"number": 200, "state": "OPEN"},
        ]

        result = service.check_epic_dependency_status(1)

        assert result["total"] == 2
        assert result["completed"] == 1
        assert result["is_ready"] is False
        assert "⏳" in result["summary_text"]

    def test_no_dependencies(self) -> None:
        """No dependencies -> total == 0, is_ready == False."""
        service = self._make_mock_service()
        service.github.get_issue_body.return_value = """## Summary
No dependencies here.
"""

        result = service.check_epic_dependency_status(1)

        assert result["total"] == 0
        assert result["completed"] == 0
        assert result["is_ready"] is False
        assert result["summary_text"] == "No dependencies"

    def test_deleted_dependency(self) -> None:
        """Deleted/inaccessible dependency should be skipped."""
        service = self._make_mock_service()
        service.github.get_issue_body.return_value = """## Dependencies
- Blocked by #100
- Blocked by #999 (deleted)
"""
        service.github.view_issue.side_effect = [
            {"number": 100, "state": "CLOSED"},
            None,  # Deleted issue
        ]

        result = service.check_epic_dependency_status(1)

        assert result["total"] == 2
        # Only #100 is completed, #999 is DELETED (not completed)
        assert result["completed"] == 1
        assert result["is_ready"] is False

    def test_network_error_on_dependency(self) -> None:
        """Network error should be treated as inaccessible."""
        service = self._make_mock_service()
        service.github.get_issue_body.return_value = """## Dependencies
- Blocked by #100
- Blocked by #200
"""
        service.github.view_issue.side_effect = [
            {"number": 100, "state": "CLOSED"},
            "network_error",
        ]

        result = service.check_epic_dependency_status(1)

        assert result["total"] == 2
        assert result["completed"] == 1
        assert result["is_ready"] is False
