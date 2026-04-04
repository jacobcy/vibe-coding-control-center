"""Unit tests for StatusQueryService."""

from unittest.mock import MagicMock

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import (
    StatusQueryService,
    is_auto_task_branch,
    is_canonical_task_branch,
    issue_priority,
)


class TestStatusQueryService:
    """Tests for StatusQueryService data aggregation."""

    def test_fetch_orchestrated_issues_cross_references_flows(self) -> None:
        """Service should cross-reference GitHub issues with flow state."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 278,
                "title": "Handoff sample",
                "labels": [{"name": "state/handoff"}],
            },
            {
                "number": 320,
                "title": "Flow done rule sync",
                "labels": [{"name": "state/ready"}],
            },
            {
                "number": 372,
                "title": "Webhook blocker",
                "labels": [{"name": "state/blocked"}],
            },
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)

        flows = [
            FlowStatusResponse(
                branch="task/issue-320",
                flow_slug="issue-320",
                flow_status="active",
                task_issue_number=320,
            ),
        ]

        result = service.fetch_orchestrated_issues(flows, queued_set=set())

        assert len(result) == 3

        # Should sort by priority: handoff (0) < ready (1) < blocked (2)
        assert result[0]["number"] == 278
        assert result[0]["state"] == IssueState.HANDOFF
        assert result[0]["flow"] is None

        assert result[1]["number"] == 320
        assert result[1]["state"] == IssueState.READY
        assert result[1]["flow"] is not None

        assert result[2]["number"] == 372
        assert result[2]["state"] == IssueState.BLOCKED

    def test_fetch_orchestrated_issues_filters_done_state(self) -> None:
        """Service should exclude issues in done state."""
        github = MagicMock()
        github.list_issues.return_value = [
            {"number": 100, "title": "Done issue", "labels": [{"name": "state/done"}]},
            {
                "number": 200,
                "title": "Ready issue",
                "labels": [{"name": "state/ready"}],
            },
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

        assert len(result) == 1
        assert result[0]["number"] == 200

    def test_fetch_orchestrated_issues_handles_github_error(self) -> None:
        """Service should handle GitHub API errors gracefully."""
        github = MagicMock()
        github.list_issues.side_effect = Exception("API error")

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

        assert result == []

    def test_fetch_worktree_map_parses_porcelain_output(self) -> None:
        """Service should parse git worktree list --porcelain output."""
        github = MagicMock()
        git = MagicMock()
        git._run.return_value = (
            "worktree /repo/.worktrees/issue-320\n"
            "branch refs/heads/task/issue-320\n\n"
            "worktree /repo/.worktrees/wt-openai-review\n"
            "branch refs/heads/openai-review\n"
        )

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_worktree_map()

        assert result["task/issue-320"] == "issue-320"
        assert result["openai-review"] == "wt-openai-review"

    def test_fetch_worktree_map_handles_error(self) -> None:
        """Service should handle git errors gracefully."""
        github = MagicMock()
        git = MagicMock()
        git._run.side_effect = Exception("Git error")

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_worktree_map()

        assert result == {}


class TestIssuePriority:
    """Tests for issue priority sorting."""

    def test_in_progress_has_highest_priority(self) -> None:
        """IN_PROGRESS should sort before all other states."""
        assert issue_priority(IssueState.IN_PROGRESS) < issue_priority(IssueState.READY)
        assert issue_priority(IssueState.IN_PROGRESS) < issue_priority(
            IssueState.BLOCKED
        )
        assert issue_priority(IssueState.IN_PROGRESS) < issue_priority(
            IssueState.FAILED
        )

    def test_ready_before_blocked(self) -> None:
        """READY should sort before BLOCKED."""
        assert issue_priority(IssueState.READY) < issue_priority(IssueState.BLOCKED)

    def test_blocked_before_failed(self) -> None:
        """BLOCKED should sort before FAILED."""
        assert issue_priority(IssueState.BLOCKED) < issue_priority(IssueState.FAILED)


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
