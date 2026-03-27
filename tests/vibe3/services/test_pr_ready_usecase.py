"""Tests for PR ready orchestration usecase."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.pr import PRResponse, PRState
from vibe3.services.pr_ready_usecase import PrReadyUsecase


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
    pr_service.mark_ready.return_value = _pr_response()
    usecase = PrReadyUsecase(pr_service=pr_service, gate_runner=gate_runner)

    pr = usecase.mark_ready(pr_number=123, yes=True)

    assert pr.number == 123
    gate_runner.assert_called_once_with(123, True)
    pr_service.mark_ready.assert_called_once_with(123)


def test_mark_ready_skips_service_when_not_confirmed() -> None:
    gate_runner = MagicMock()
    pr_service = MagicMock()
    confirmer = MagicMock(return_value=False)
    usecase = PrReadyUsecase(
        pr_service=pr_service,
        gate_runner=gate_runner,
        confirmer=confirmer,
    )

    with pytest.raises(RuntimeError, match="aborted by user"):
        usecase.mark_ready(pr_number=123, yes=False)

    gate_runner.assert_called_once_with(123, False)
    confirmer.assert_called_once_with(123)
    pr_service.mark_ready.assert_not_called()
