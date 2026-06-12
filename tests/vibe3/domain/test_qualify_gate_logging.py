"""Regression tests for qualify gate operator-facing logs."""

from unittest.mock import Mock, patch

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models.coordination_truth import CoordinationTruth
from vibe3.models.data_source import DataSource
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


def test_blocked_skip_log_includes_truth_details() -> None:
    store = Mock(db_path=":memory:")
    service = QualifyGateService(
        config=OrchestraConfig(repo="test/repo"),
        github=Mock(),
        store=store,
        flow_manager=Mock(),
    )
    issue = IssueInfo(
        number=123,
        title="Test Issue",
        state=IssueState.IN_PROGRESS,
        labels=["state/in-progress"],
        assignees=["alice"],
    )
    truth = CoordinationTruth(
        projection_state="blocked",
        projection_state_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_reason="needs human approval",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
        blocked_by_issues=[456],
        blocked_by_issue_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    with (
        patch.object(
            service._coordination_resolver,
            "resolve_coordination",
            return_value=truth,
        ),
        patch(
            "vibe3.observability.orchestra_log.append_orchestra_event"
        ) as append_event,
    ):
        result = service.run_qualify_gate(
            issue=issue,
            branch="task/issue-123-test",
            flow_state={"flow_status": "blocked", "blocked_reason": "stale"},
            labels=["state/blocked"],
            trigger_state=IssueState.IN_PROGRESS,
        )

    assert result is None
    message = append_event.call_args[0][1]
    expected_parts = [
        "blocked_reason=needs human approval",
        "blocked_by_issue=#456",
        "projection_state=blocked",
        "projection_source=fallback",
        "blocked_reason_source=fallback",
        "local_flow_status=blocked",
        "label_blocked=True",
    ]
    assert all(part in message for part in expected_parts)


def test_blocked_skip_log_reports_aligned_label_state() -> None:
    service = QualifyGateService(
        config=OrchestraConfig(repo="test/repo"),
        github=Mock(),
        store=Mock(db_path=":memory:"),
        flow_manager=Mock(),
    )
    truth = CoordinationTruth(
        blocked_reason="remote block",
        blocked_reason_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    with (
        patch.object(
            service._coordination_resolver,
            "resolve_coordination",
            return_value=truth,
        ),
        patch("vibe3.services.LabelService") as label_service,
        patch(
            "vibe3.observability.orchestra_log.append_orchestra_event"
        ) as append_event,
    ):
        result = service.run_qualify_gate(
            issue=IssueInfo(
                number=123,
                title="Test Issue",
                state=IssueState.IN_PROGRESS,
                labels=["state/in-progress"],
                assignees=["alice"],
            ),
            branch="task/issue-123-test",
            flow_state={"flow_status": "active"},
            labels=["state/in-progress"],
            trigger_state=IssueState.IN_PROGRESS,
        )

    assert result is None
    label_service.return_value.confirm_issue_state.assert_called_once()
    assert "label_blocked=True" in append_event.call_args[0][1]
