"""Tests for execution pipeline lifecycle observability."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.review_runner import AgentOptions, AgentResult
from vibe3.services.execution_pipeline import ExecutionRequest, run_execution_pipeline


def _make_request() -> ExecutionRequest:
    return ExecutionRequest(
        role="executor",
        context_builder=lambda: "# prompt",
        options_builder=lambda: AgentOptions(agent="executor"),
        task="ship it",
        handoff_kind="run",
    )


@patch("vibe3.services.execution_pipeline.record_handoff_unified")
@patch("vibe3.services.execution_pipeline.execute_agent")
@patch(
    "vibe3.services.execution_pipeline.load_session_id", return_value="sess-existing"
)
def test_run_execution_pipeline_marks_started_before_execute_agent(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    store = MagicMock()
    mock_record.return_value = Path("/tmp/run-report.md")

    with (
        patch(
            "vibe3.services.execution_pipeline.SQLiteClient",
            return_value=store,
            create=True,
        ),
        patch(
            "vibe3.clients.git_client.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/demo")
            ),
            create=True,
        ),
    ):

        def _side_effect(*_args, **_kwargs):
            event_types = [call.args[1] for call in store.add_event.call_args_list]
            assert "run_started" in event_types
            started_state = store.update_flow_state.call_args_list[0].kwargs
            assert started_state["executor_status"] == "running"
            return AgentResult(
                exit_code=0, stdout="done", stderr="", session_id="sess-new"
            )

        mock_execute.side_effect = _side_effect

        run_execution_pipeline(_make_request())


@patch("vibe3.services.execution_pipeline.record_handoff_unified")
@patch("vibe3.services.execution_pipeline.execute_agent")
@patch(
    "vibe3.services.execution_pipeline.load_session_id", return_value="sess-existing"
)
def test_run_execution_pipeline_marks_completed_with_report_ref(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    store = MagicMock()
    mock_execute.return_value = AgentResult(
        exit_code=0,
        stdout="done",
        stderr="",
        session_id="sess-new",
    )
    mock_record.return_value = Path("/tmp/run-report.md")

    with (
        patch(
            "vibe3.services.execution_pipeline.SQLiteClient",
            return_value=store,
            create=True,
        ),
        patch(
            "vibe3.clients.git_client.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/demo")
            ),
            create=True,
        ),
    ):
        run_execution_pipeline(_make_request())

    completed_call = next(
        call
        for call in store.add_event.call_args_list
        if call.args[1] == "run_completed"
    )
    assert completed_call.kwargs["refs"]["ref"] == "/tmp/run-report.md"
    completed_state = store.update_flow_state.call_args_list[-1].kwargs
    assert completed_state["executor_status"] == "done"
    assert completed_state["execution_completed_at"] is not None


@patch("vibe3.services.execution_pipeline.record_handoff_unified")
@patch("vibe3.services.execution_pipeline.execute_agent")
@patch(
    "vibe3.services.execution_pipeline.load_session_id", return_value="sess-existing"
)
def test_run_execution_pipeline_marks_aborted_when_execution_fails(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    store = MagicMock()
    mock_execute.side_effect = RuntimeError("wrapper exploded")

    with (
        patch(
            "vibe3.services.execution_pipeline.SQLiteClient",
            return_value=store,
            create=True,
        ),
        patch(
            "vibe3.clients.git_client.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/demo")
            ),
            create=True,
        ),
        pytest.raises(RuntimeError, match="wrapper exploded"),
    ):
        run_execution_pipeline(_make_request())

    mock_record.assert_not_called()
    aborted_call = next(
        call for call in store.add_event.call_args_list if call.args[1] == "run_aborted"
    )
    assert "wrapper exploded" in aborted_call.kwargs["detail"]
    aborted_state = store.update_flow_state.call_args_list[-1].kwargs
    assert aborted_state["executor_status"] == "crashed"
    assert aborted_state["execution_completed_at"] is not None


@patch("vibe3.services.execution_pipeline.record_handoff_unified")
@patch("vibe3.services.execution_pipeline.execute_agent")
@patch(
    "vibe3.services.execution_pipeline.load_session_id", return_value="sess-existing"
)
def test_run_execution_pipeline_skips_lifecycle_when_async_child(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    """Async child (VIBE3_ASYNC_CHILD=1) must NOT record lifecycle events.

    The parent AsyncExecutionService owns lifecycle events for async runs.
    Recording them in the child creates duplicate started/completed/aborted
    entries in the flow timeline (issue #271).
    """
    store = MagicMock()
    mock_execute.return_value = AgentResult(
        exit_code=0,
        stdout="done",
        stderr="",
        session_id="sess-new",
    )
    mock_record.return_value = Path("/tmp/run-report.md")

    with (
        patch.dict("os.environ", {"VIBE3_ASYNC_CHILD": "1"}),
        patch(
            "vibe3.services.execution_pipeline.SQLiteClient",
            return_value=store,
            create=True,
        ),
        patch(
            "vibe3.clients.git_client.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/demo")
            ),
            create=True,
        ),
    ):
        run_execution_pipeline(_make_request())

    store.add_event.assert_not_called()
    store.update_flow_state.assert_not_called()
    mock_record.assert_called_once()


@patch("vibe3.services.execution_pipeline.record_handoff_unified")
@patch("vibe3.services.execution_pipeline.execute_agent")
@patch(
    "vibe3.services.execution_pipeline.load_session_id", return_value="sess-existing"
)
def test_run_execution_pipeline_async_child_no_aborted_on_failure(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    """Async child must NOT record aborted event even on execution failure."""
    store = MagicMock()
    mock_execute.side_effect = RuntimeError("Plan file not found: nonexistent.md")

    with (
        patch.dict("os.environ", {"VIBE3_ASYNC_CHILD": "1"}),
        patch(
            "vibe3.services.execution_pipeline.SQLiteClient",
            return_value=store,
            create=True,
        ),
        patch(
            "vibe3.clients.git_client.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/demo")
            ),
            create=True,
        ),
        pytest.raises(RuntimeError, match="Plan file not found"),
    ):
        run_execution_pipeline(_make_request())

    store.add_event.assert_not_called()
    store.update_flow_state.assert_not_called()
    mock_record.assert_not_called()
