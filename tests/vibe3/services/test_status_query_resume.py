"""Unit tests for StatusQueryService resume operations."""

from unittest.mock import MagicMock

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import StatusQueryService


class TestStatusQueryServiceResume:
    """Tests for StatusQueryService resume candidate operations."""

    def test_status_ignores_resume_comment_for_failed_reason(
        self,
    ) -> None:
        """status 快照不把 resume comment 当作新的 failed reason。"""
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
                        "[resume] 已从 state/failed 继续到 state/handoff。\n\n"
                        "manager 将重新判断现场并决定下一步。\n\n"
                        "原因:quota resumed"
                    ),
                },
            ]
        }

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)
        result = service.fetch_orchestrated_issues([], queued_set=set())

        # Should extract "quota exhausted", not "quota resumed"
        assert result[0]["failed_reason"] == "quota exhausted"


class TestResumeCandidates:
    """Tests for unified resume candidate query."""

    def test_fetch_resume_candidates_returns_failed_and_recoverable_blocked_issues(
        self,
    ) -> None:
        """Failed 和 stale blocked issue 都应进入候选，resume_kind 明确区分来源。"""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 439,
                "title": "Manager backend regression",
                "labels": [{"name": "state/failed"}],
            },
            {
                "number": 301,
                "title": "Dependency available",
                "labels": [{"name": "state/blocked"}],
            },
            {
                "number": 441,
                "title": "API timeout",
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

        # Mock flows
        flow_439 = MagicMock(spec=FlowStatusResponse)
        flow_439.plan_ref = "docs/plans/issue-439.md"
        flow_439.branch = "task/issue-439"
        flow_439.task_issue_number = 439
        flow_439.flow_status = "active"

        flow_441 = MagicMock(spec=FlowStatusResponse)
        flow_441.plan_ref = None
        flow_441.branch = "task/issue-441"
        flow_441.task_issue_number = 441
        flow_441.flow_status = "active"

        # Stale blocked flow
        flow_301 = MagicMock(spec=FlowStatusResponse)
        flow_301.plan_ref = None
        flow_301.branch = "task/issue-301"
        flow_301.task_issue_number = 301
        flow_301.flow_status = "stale"

        flows = [flow_439, flow_441]
        stale_flows = [flow_301]

        result = service.fetch_resume_candidates(flows=flows, stale_flows=stale_flows)

        assert len(result) == 3

        # Verify failed candidates
        failed_439 = next((r for r in result if r["number"] == 439), None)
        assert failed_439 is not None
        assert failed_439["state"] == IssueState.FAILED
        assert failed_439["resume_kind"] == "failed"
        assert failed_439["flow"] is not None
        assert failed_439["flow"].plan_ref == "docs/plans/issue-439.md"

        failed_441 = next((r for r in result if r["number"] == 441), None)
        assert failed_441 is not None
        assert failed_441["state"] == IssueState.FAILED
        assert failed_441["resume_kind"] == "failed"

        # Verify blocked candidate
        blocked_301 = next((r for r in result if r["number"] == 301), None)
        assert blocked_301 is not None
        assert blocked_301["state"] == IssueState.BLOCKED
        assert blocked_301["resume_kind"] == "blocked"
        assert blocked_301["flow"] is not None
        assert blocked_301["flow"].flow_status == "stale"

    def test_fetch_resume_candidates_excludes_nonrecoverable_blocked_issues(
        self,
    ) -> None:
        """非 stale blocked、ready、handoff、done issue 不进入候选。"""
        github = MagicMock()
        github.list_issues.return_value = [
            {
                "number": 302,
                "title": "Active blocked",
                "labels": [{"name": "state/blocked"}],
            },
            {
                "number": 303,
                "title": "Ready issue",
                "labels": [{"name": "state/ready"}],
            },
            {
                "number": 304,
                "title": "Handoff issue",
                "labels": [{"name": "state/handoff"}],
            },
            {
                "number": 305,
                "title": "Done issue",
                "labels": [{"name": "state/done"}],
            },
        ]

        git = MagicMock()
        git._run.return_value = ""

        service = StatusQueryService(github_client=github, git_client=git)

        # Active blocked flow (not stale, should be excluded)
        flow_302 = MagicMock(spec=FlowStatusResponse)
        flow_302.branch = "task/issue-302"
        flow_302.task_issue_number = 302
        flow_302.flow_status = "active"

        stale_flows = []

        result = service.fetch_resume_candidates(
            flows=[flow_302], stale_flows=stale_flows
        )

        assert len(result) == 0
