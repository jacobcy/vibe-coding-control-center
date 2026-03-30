"""Tests for PR query command orchestration usecase."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_query_usecase import PrQueryUsecase


def _pr_response() -> PRResponse:
    return PRResponse(
        number=123,
        title="Test PR",
        body="Body",
        state=PRState.OPEN,
        head_branch="task/demo",
        base_branch="main",
        url="https://example.com/pr/123",
    )


def test_resolve_target_uses_flow_pr_when_inputs_missing() -> None:
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    pr_service = MagicMock()
    pr_service.store.get_flow_state.return_value = {"pr_number": 123}
    usecase = PrQueryUsecase(pr_service=pr_service, flow_service=flow_service)

    target = usecase.resolve_target(pr_number=None, branch=None)

    assert target.pr_number == 123
    assert target.branch is None
    assert target.current_branch == "task/demo"
    assert target.from_flow is True


def test_build_missing_pr_message_includes_bind_hint_when_task_missing() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=None,
    )
    usecase = PrQueryUsecase(pr_service=MagicMock(), flow_service=flow_service)

    message = usecase.build_missing_pr_message(
        pr_number=None,
        branch=None,
        current_branch="task/demo",
    )

    assert "No PR found for current branch 'task/demo'" in message
    assert "vibe3 flow bind <issue> --role task" in message


def test_load_analysis_summary_returns_counts() -> None:
    usecase = PrQueryUsecase(
        pr_service=MagicMock(),
        flow_service=MagicMock(),
        inspect_runner=lambda args: {
            "score": {"level": "medium", "score": 6},
            "impact": {"changed_files": ["a.py", "b.py"]},
            "dag": {"impacted_modules": ["svc.a"]},
        },
    )

    analysis = usecase.load_analysis_summary(123)

    assert analysis["risk_level"] == "medium"
    assert analysis["risk_score"] == 6
    assert analysis["changed_files_count"] == 2
    assert analysis["impacted_modules_count"] == 1


def test_build_output_payload_merges_pr_and_analysis() -> None:
    usecase = PrQueryUsecase(pr_service=MagicMock(), flow_service=MagicMock())

    payload = usecase.build_output_payload(
        _pr_response(),
        analysis_summary={"risk_level": "low", "risk_score": 2},
    )

    assert payload["number"] == 123
    assert payload["analysis"] == {"risk_level": "low", "risk_score": 2}


def test_fetch_pr_raises_when_missing() -> None:
    pr_service = MagicMock()
    pr_service.get_pr.return_value = None
    usecase = PrQueryUsecase(pr_service=pr_service, flow_service=MagicMock())

    with pytest.raises(LookupError, match="PR not found"):
        usecase.fetch_pr(pr_number=123, branch=None)


def test_fetch_pr_falls_back_to_current_branch_when_cached_pr_missing() -> None:
    pr_service = MagicMock()
    pr_service.get_pr.side_effect = [None, _pr_response()]
    usecase = PrQueryUsecase(pr_service=pr_service, flow_service=MagicMock())

    result = usecase.fetch_pr(
        pr_number=999,
        branch=None,
        current_branch="task/demo",
    )

    assert result.number == 123
    assert pr_service.get_pr.call_count == 2
    first_call = pr_service.get_pr.call_args_list[0]
    second_call = pr_service.get_pr.call_args_list[1]
    assert first_call.args == (999, None)
    assert second_call.kwargs == {"branch": "task/demo"}
