"""Unit tests for StatusQueryService fetch operations."""

from unittest.mock import MagicMock

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import StatusQueryService


class TestStatusQueryServiceFetch:
    """Tests for StatusQueryService fetch operations."""

    def test_fetch_orchestrated_issues_cross_references_flows(self) -> None:
        """Service should cross-reference GitHub issues with flow state."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 278,
                "title": "Handoff sample",
                "labels": [{"name": "state/handoff"}],
                "assignees": [{"login": "manager-bot"}],
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

        # New sorting: READY issues first, then others by operational urgency
        # READY 320 comes first, then HANDOFF 278, then BLOCKED 372
        assert result[0]["number"] == 320
        assert result[0]["state"] == IssueState.READY
        assert result[0]["flow"] is not None

        assert result[1]["number"] == 278
        assert result[1]["state"] == IssueState.HANDOFF
        assert result[1]["assignee"] == "manager-bot"
        assert result[1]["flow"] is None

        assert result[2]["number"] == 372
        assert result[2]["state"] == IssueState.BLOCKED

    def test_fetch_orchestrated_issues_includes_done_state(self) -> None:
        """Service should include issues in done state for PR section.

        Note: DONE state filtering moved to UI layer (see f7935e78).
        This allows flows with PRs to be shown in task status dashboard.
        """
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

        # Both issues should be included (DONE filtering happens at UI layer)
        assert len(result) == 2
        # READY issues are sorted first, then other issues by priority
        assert result[0]["number"] == 200  # Ready issue (READY comes first)
        assert result[1]["number"] == 100  # Done issue (after READY)

    def test_fetch_orchestrated_issues_handles_github_error(self) -> None:
        """Service should handle GitHub API errors gracefully."""
        github = MagicMock()
        github.list_issues.side_effect = Exception("API error")

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

        assert result == []

    def test_fetch_orchestrated_issues_ignores_blank_assignee_login(self) -> None:
        """Blank assignee login should normalize to None."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 210,
                "title": "Ready issue with blank assignee",
                "labels": [{"name": "state/ready"}],
                "assignees": [{"login": "   "}],
            }
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

        assert len(result) == 1
        assert result[0]["assignee"] is None

    def test_fetch_orchestrated_issues_does_not_require_config_attr(self) -> None:
        """Service should not depend on a missing self.config attribute."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Recovered handoff",
                "labels": [{"name": "state/handoff"}],
            }
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

        github.list_issues.assert_called_once_with(
            limit=100,
            state="open",
            assignee=None,
            repo=None,
        )
        assert len(result) == 1
        assert result[0]["number"] == 439
        assert result[0]["state"] == IssueState.HANDOFF

    def test_fetch_orchestrated_issues_extracts_failed_reason(self) -> None:
        """FAILED issues should carry failed_reason from flow state."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "labels": [{"name": "state/failed"}],
            }
        ]

        git = MagicMock()
        git._run.return_value = ""

        # Create flow with failed_reason
        flow = MagicMock(spec=FlowStatusResponse)
        flow.branch = "task/issue-439"
        flow.task_issue_number = 439
        flow.failed_reason = "quota exhausted"

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues(
            [flow], queued_set=set(), stale_flows=[]
        )

        assert len(result) == 1
        assert result[0]["state"] == IssueState.FAILED
        assert result[0]["failed_reason"] == "quota exhausted"

    def test_fetch_orchestrated_issues_ignores_recovery_comments_for_failed_reason(
        self,
    ) -> None:
        """FAILED reason comes from flow state, not GitHub comments."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "labels": [{"name": "state/failed"}],
            }
        ]

        git = MagicMock()
        git._run.return_value = ""

        # Create flow with failed_reason (ignores GitHub comments now)
        flow = MagicMock(spec=FlowStatusResponse)
        flow.branch = "task/issue-439"
        flow.task_issue_number = 439
        flow.failed_reason = "quota exhausted"

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues(
            [flow], queued_set=set(), stale_flows=[]
        )

        assert result[0]["failed_reason"] == "quota exhausted"

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

    def test_stale_flow_associated_with_blocked_issue(self) -> None:
        """stale flow 应出现在 blocked issue 的 flow 字段，而不是 None。"""

        def _make_flow(branch: str, issue_number: int, flow_status: str = "active"):
            f = MagicMock(spec=FlowStatusResponse)
            f.branch = branch
            f.task_issue_number = issue_number
            f.flow_status = flow_status
            return f

        active_flows = []
        stale_flows = [_make_flow("task/issue-301", 301, "stale")]

        github = MagicMock()
        github.list_issues.return_value = [
            {"number": 301, "title": "feat", "labels": [{"name": "state/blocked"}]}
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)

        # We need to bypass __init__ or ensure it doesn't fail.
        # The original code uses: svc = StatusQueryService.__new__(StatusQueryService)
        # But here we can just use the regular constructor since we mocked clients.

        result = service.fetch_orchestrated_issues(
            active_flows, queued_set=set(), stale_flows=stale_flows
        )

        assert len(result) == 1
        item = result[0]
        assert item["flow"] is not None
        assert item["flow"].branch == "task/issue-301"
        assert item["flow"].flow_status == "stale"

    def test_active_flow_takes_precedence_over_stale(self) -> None:
        """同一 issue 同时有 active 和 stale flow 时，active 优先。"""

        def _make_flow(branch: str, issue_number: int, flow_status: str = "active"):
            f = MagicMock(spec=FlowStatusResponse)
            f.branch = branch
            f.task_issue_number = issue_number
            f.flow_status = flow_status
            return f

        active_flow = _make_flow("task/issue-301", 301, "active")
        stale_flow = _make_flow("task/issue-301-old", 301, "stale")

        github = MagicMock()
        github.list_issues.return_value = [
            {"number": 301, "title": "feat", "labels": [{"name": "state/blocked"}]}
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)

        result = service.fetch_orchestrated_issues(
            [active_flow], queued_set=set(), stale_flows=[stale_flow]
        )

        assert result[0]["flow"].flow_status == "active"

    def test_fetch_orchestrated_issues_excludes_manual_flow_issue(self) -> None:
        """Manual flow branches must not be treated as orchestra issues."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 443,
                "title": "Manual debug scene",
                "labels": [{"name": "state/in-progress"}],
            }
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        flows = [
            FlowStatusResponse(
                branch="debug/service-gap-analysis",
                flow_slug="service-gap-analysis",
                flow_status="done",
                task_issue_number=443,
            ),
        ]

        result = service.fetch_orchestrated_issues(flows, queued_set=set())

        assert result == []

    def test_fetch_orchestrated_issues_prefers_task_flow_over_manual_flow(self) -> None:
        """Canonical task flow must win over manual flow for the same issue."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 443,
                "title": "Canonical task should remain visible",
                "labels": [{"name": "state/in-progress"}],
            }
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        flows = [
            FlowStatusResponse(
                branch="debug/service-gap-analysis",
                flow_slug="service-gap-analysis",
                flow_status="active",
                task_issue_number=443,
            ),
            FlowStatusResponse(
                branch="task/issue-443",
                flow_slug="issue-443",
                flow_status="active",
                task_issue_number=443,
            ),
        ]

        result = service.fetch_orchestrated_issues(flows, queued_set=set())

        assert len(result) == 1
        assert result[0]["flow"] is not None
        assert result[0]["flow"].branch == "task/issue-443"
