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
        """FAILED issues should carry a human-readable error reason."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "labels": [{"name": "state/failed"}],
            }
        ]
        github.view_issue.return_value = {
            "comments": [
                {
                    "body": (
                        "[manager] 管理执行报错,已切换为 state/failed。\n\n"
                        "原因:quota exhausted"
                    ),
                }
            ]
        }

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

        assert len(result) == 1
        assert result[0]["state"] == IssueState.FAILED
        assert result[0]["failed_reason"] == "quota exhausted"

    def test_fetch_orchestrated_issues_ignores_recovery_comments_for_failed_reason(
        self,
    ) -> None:
        """FAILED reason ignores recovery comments, prefers failure reports."""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "labels": [{"name": "state/failed"}],
            }
        ]
        github.view_issue.return_value = {
            "comments": [
                {
                    "body": (
                        "[manager] 管理执行报错,已切换为 state/failed。\n\n"
                        "原因:quota exhausted"
                    ),
                },
                {
                    "body": (
                        "[recovery] 已从 state/failed 恢复到 state/handoff。\n\n"
                        "原因:manual relabel"
                    ),
                },
            ]
        }

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

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

    def test_fetch_failed_resume_candidates_returns_open_failed_issues(
        self,
    ) -> None:
        """只返回 open 且 label 为 state/failed 的 issue，携带 flow.plan_ref。"""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "labels": [{"name": "state/failed"}],
            },
            {
                "number": 440,
                "title": "Ready issue",
                "labels": [{"name": "state/ready"}],
            },
            {
                "number": 441,
                "title": "Another failed issue",
                "labels": [{"name": "state/failed"}],
            },
        ]
        github.view_issue.return_value = {
            "comments": [
                {
                    "body": (
                        "[manager] 管理执行报错,已切换为 state/failed。\n\n"
                        "原因:quota exhausted"
                    )
                }
            ]
        }

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)

        # Mock flow with plan_ref for issue 439
        flow_439 = MagicMock(spec=FlowStatusResponse)
        flow_439.plan_ref = "docs/plans/issue-439.md"
        flow_439.branch = "task/issue-439"
        flow_439.task_issue_number = 439

        # Mock flow without plan_ref for issue 441
        flow_441 = MagicMock(spec=FlowStatusResponse)
        flow_441.plan_ref = None
        flow_441.branch = "task/issue-441"
        flow_441.task_issue_number = 441

        flows = [flow_439, flow_441]

        result = service.fetch_failed_resume_candidates(flows=flows)

        assert len(result) == 2
        assert result[0]["number"] == 439
        assert result[0]["state"] == IssueState.FAILED
        assert result[0]["flow"] is not None
        assert result[0]["flow"].plan_ref == "docs/plans/issue-439.md"
        assert result[1]["number"] == 441
        assert result[1]["state"] == IssueState.FAILED

    def test_fetch_failed_resume_candidates_excludes_resumed_or_non_failed(
        self,
    ) -> None:
        """已恢复或非 failed 的 issue 不进入候选。"""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Resumed issue",
                "labels": [{"name": "state/handoff"}],  # Already resumed
            },
            {
                "number": 440,
                "title": "Blocked issue",
                "labels": [{"name": "state/blocked"}],
            },
            {
                "number": 441,
                "title": "Ready issue",
                "labels": [{"name": "state/ready"}],
            },
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_failed_resume_candidates(flows=[])

        assert len(result) == 0


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
