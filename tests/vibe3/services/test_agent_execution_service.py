"""Tests for shared agent execution service."""

from unittest.mock import MagicMock, patch

from vibe3.agents.session_service import execute_agent, load_session_id
from vibe3.models.review_runner import AgentOptions, AgentResult


@patch("vibe3.agents.session_service.FlowService")
@patch("vibe3.agents.session_service.GitClient")
def test_load_session_id_returns_role_session(git_cls, flow_service_cls) -> None:
    git_cls.return_value.get_current_branch.return_value = "task/demo"
    flow_status = MagicMock(executor_session_id="sess-123")
    flow_service_cls.return_value.get_flow_status.return_value = flow_status

    session_id = load_session_id("executor")

    assert session_id == "sess-123"


@patch("vibe3.agents.session_service.run_review_agent")
def test_execute_agent_returns_effective_session_id(mock_run) -> None:
    mock_run.return_value = AgentResult(
        exit_code=0,
        stdout="ok",
        stderr="",
        session_id="new-session-id",
    )

    result = execute_agent(
        AgentOptions(agent="executor"),
        "# prompt",
        task="do it",
        dry_run=False,
        session_id="old-session-id",
    )

    assert result.stdout == "ok"
    assert result.session_id == "new-session-id"
