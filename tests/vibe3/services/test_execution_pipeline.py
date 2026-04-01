"""Tests for execution pipeline lifecycle observability."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.pipeline import ExecutionRequest, run_execution_pipeline
from vibe3.models.review_runner import AgentOptions, AgentResult


def _make_request() -> ExecutionRequest:
    return ExecutionRequest(
        role="executor",
        context_builder=lambda: "# prompt",
        options_builder=lambda: AgentOptions(agent="executor"),
        task="ship it",
        handoff_kind="run",
    )


@patch("vibe3.agents.pipeline.record_handoff_unified")
@patch("vibe3.agents.backends.codeagent.CodeagentBackend.run")
@patch("vibe3.agents.pipeline.load_session_id", return_value="sess-existing")
def test_run_execution_pipeline_marks_started_before_execute_agent(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    store = MagicMock()
    mock_record.return_value = Path("/tmp/run-report.md")

    with (
        patch(
            "vibe3.agents.pipeline.SQLiteClient",
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
            # persist_execution_lifecycle_event is a function, not a store method
            return AgentResult(
                exit_code=0, stdout="done", stderr="", session_id="sess-new"
            )

        mock_execute.side_effect = _side_effect

        # We need to patch persist_execution_lifecycle_event because
        # it's imported in pipeline.py
        with patch(
            "vibe3.agents.pipeline.persist_execution_lifecycle_event"
        ) as mock_persist:
            run_execution_pipeline(_make_request())

            event_types = [call.args[3] for call in mock_persist.call_args_list]
            assert "started" in event_types


@patch("vibe3.agents.pipeline.record_handoff_unified")
@patch("vibe3.agents.backends.codeagent.CodeagentBackend.run")
@patch("vibe3.agents.pipeline.load_session_id", return_value="sess-existing")
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
            "vibe3.agents.pipeline.SQLiteClient",
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
        patch(
            "vibe3.agents.pipeline.persist_execution_lifecycle_event"
        ) as mock_persist,
    ):
        run_execution_pipeline(_make_request())

        completed_call = next(
            call for call in mock_persist.call_args_list if call.args[3] == "completed"
        )
        assert completed_call.kwargs["refs"]["ref"] == "/tmp/run-report.md"


@patch("vibe3.agents.pipeline.record_handoff_unified")
@patch("vibe3.agents.backends.codeagent.CodeagentBackend.run")
@patch("vibe3.agents.pipeline.load_session_id", return_value="sess-existing")
def test_run_execution_pipeline_marks_aborted_when_execution_fails(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    store = MagicMock()
    mock_execute.side_effect = RuntimeError("wrapper exploded")

    with (
        patch(
            "vibe3.agents.pipeline.SQLiteClient",
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
        patch(
            "vibe3.agents.pipeline.persist_execution_lifecycle_event"
        ) as mock_persist,
        pytest.raises(RuntimeError, match="wrapper exploded"),
    ):
        run_execution_pipeline(_make_request())

    mock_record.assert_not_called()
    aborted_call = next(
        call for call in mock_persist.call_args_list if call.args[3] == "aborted"
    )
    assert "wrapper exploded" in aborted_call.kwargs["refs"]["reason"]


@patch("vibe3.agents.pipeline.record_handoff_unified")
@patch("vibe3.agents.backends.codeagent.CodeagentBackend.run")
@patch("vibe3.agents.pipeline.load_session_id", return_value="sess-existing")
def test_run_execution_pipeline_skips_lifecycle_when_async_child(
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
        patch.dict("os.environ", {"VIBE3_ASYNC_CHILD": "1"}),
        patch(
            "vibe3.agents.pipeline.SQLiteClient",
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
        patch(
            "vibe3.agents.pipeline.persist_execution_lifecycle_event"
        ) as mock_persist,
    ):
        run_execution_pipeline(_make_request())

    mock_persist.assert_not_called()
    mock_record.assert_called_once()


@patch("vibe3.agents.pipeline.record_handoff_unified")
@patch("vibe3.agents.backends.codeagent.CodeagentBackend.run")
@patch("vibe3.agents.pipeline.load_session_id", return_value="sess-existing")
def test_run_execution_pipeline_async_child_no_aborted_on_failure(
    _mock_session,
    mock_execute,
    mock_record,
) -> None:
    store = MagicMock()
    mock_execute.side_effect = RuntimeError("Plan file not found: nonexistent.md")

    with (
        patch.dict("os.environ", {"VIBE3_ASYNC_CHILD": "1"}),
        patch(
            "vibe3.agents.pipeline.SQLiteClient",
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
        patch(
            "vibe3.agents.pipeline.persist_execution_lifecycle_event"
        ) as mock_persist,
        pytest.raises(RuntimeError, match="Plan file not found"),
    ):
        run_execution_pipeline(_make_request())

    mock_persist.assert_not_called()
    mock_record.assert_not_called()
