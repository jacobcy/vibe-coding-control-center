"""Qualify gate must not turn PR observation into normal state progression."""

from unittest.mock import Mock, patch

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models import (
    CoordinationTruth,
    DataSource,
    IssueInfo,
    IssueState,
    OrchestraConfig,
)


def test_open_pr_with_running_worker_does_not_advance_flow_status() -> None:
    github = Mock()
    store = Mock()
    store.db_path = ":memory:"
    flow_manager = Mock()
    service = QualifyGateService(
        config=OrchestraConfig(repo="test/repo"),
        github=github,
        store=store,
        flow_manager=flow_manager,
    )
    issue = IssueInfo(
        number=123,
        title="Test Issue",
        state=IssueState.IN_PROGRESS,
        labels=["state/in-progress"],
        assignees=["alice"],
    )
    flow_state = {
        "flow_status": "active",
        "planner_status": "running",
        "pr_ref": "https://example.test/pull/42",
    }
    truth = CoordinationTruth(worktree_path=None)

    with (
        patch.object(
            service._coordination_resolver,
            "resolve_coordination",
            return_value=truth,
        ),
        patch("vibe3.services.FlowStatusService") as flow_status_cls,
    ):
        result = service.run_qualify_gate(
            issue=issue,
            branch="task/issue-123",
            flow_state=flow_state,
            labels=issue.labels,
            trigger_state=IssueState.IN_PROGRESS,
        )

    assert result == IssueState.IN_PROGRESS
    github.list_prs_for_branch.assert_not_called()
    flow_status_cls.assert_not_called()


def test_authoritative_blocked_truth_rejects_without_resume_inference() -> None:
    github = Mock()
    store = Mock()
    store.db_path = ":memory:"
    service = QualifyGateService(
        config=OrchestraConfig(repo="test/repo"),
        github=github,
        store=store,
        flow_manager=Mock(),
    )
    issue = IssueInfo(
        number=124,
        title="Blocked truth",
        state=IssueState.READY,
        labels=["state/ready"],
    )
    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_reason="waiting for dependency",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    with (
        patch.object(
            service._coordination_resolver,
            "resolve_coordination",
            return_value=truth,
        ),
        patch("vibe3.domain.qualify_gate.BlockedStateService") as blocked_cls,
    ):
        result = service.run_qualify_gate(
            issue=issue,
            branch="task/issue-124",
            flow_state=None,
            labels=issue.labels,
            trigger_state=IssueState.READY,
        )

    assert result is None
    blocked_cls.assert_not_called()
