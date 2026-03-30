"""Tests for PR ready orchestration usecase."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_ready_usecase import PrReadyAbortedError, PrReadyUsecase


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


def test_mark_ready_runs_gates_then_marks_ready() -> None:
    gate_runner = MagicMock()
    pr_service = MagicMock()
    draft_pr = _pr_response().model_copy(update={"draft": True})
    ready_pr = _pr_response().model_copy(update={"draft": False})
    pr_service.get_pr.return_value = draft_pr
    pr_service.mark_ready.return_value = ready_pr
    pr_service.store.get_issue_links.return_value = [
        {"branch": "task/demo", "issue_number": 220, "issue_role": "task"}
    ]
    label_service = MagicMock()
    usecase = PrReadyUsecase(pr_service=pr_service, gate_runner=gate_runner)
    usecase.label_service = label_service

    pr = usecase.mark_ready(pr_number=123, yes=True)

    assert pr.number == 123
    gate_runner.assert_called_once_with(123, True)
    pr_service.mark_ready.assert_called_once_with(123)
    label_service.confirm_issue_state.assert_called_once()


def test_mark_ready_skips_service_when_not_confirmed() -> None:
    gate_runner = MagicMock()
    pr_service = MagicMock()
    pr_service.get_pr.return_value = _pr_response().model_copy(update={"draft": True})
    confirmer = MagicMock(return_value=False)
    usecase = PrReadyUsecase(
        pr_service=pr_service,
        gate_runner=gate_runner,
        confirmer=confirmer,
    )

    with pytest.raises(PrReadyAbortedError, match="aborted by user"):
        usecase.mark_ready(pr_number=123, yes=False)

    gate_runner.assert_called_once_with(123, False)
    confirmer.assert_called_once_with(123)
    pr_service.mark_ready.assert_not_called()


def test_mark_ready_already_ready_skips_gates() -> None:
    gate_runner = MagicMock()
    pr_service = MagicMock()
    ready_pr = _pr_response().model_copy(update={"draft": False, "is_ready": True})
    pr_service.get_pr.return_value = ready_pr
    pr_service.mark_ready.return_value = ready_pr
    pr_service.store.get_issue_links.return_value = [
        {"branch": "task/demo", "issue_number": 220, "issue_role": "task"}
    ]
    label_service = MagicMock()
    usecase = PrReadyUsecase(pr_service=pr_service, gate_runner=gate_runner)
    usecase.label_service = label_service

    pr = usecase.mark_ready(pr_number=123, yes=False)

    assert pr.number == 123
    gate_runner.assert_not_called()
    pr_service.mark_ready.assert_called_once_with(123)
    label_service.confirm_issue_state.assert_called_once()
