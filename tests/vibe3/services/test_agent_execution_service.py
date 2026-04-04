"""Tests for shared agent execution service."""

from unittest.mock import MagicMock, patch

from vibe3.agents.session_service import load_session_id


@patch("vibe3.agents.session_service.FlowService")
@patch("vibe3.agents.session_service.GitClient")
def test_load_session_id_returns_role_session(git_cls, flow_service_cls) -> None:
    git_cls.return_value.get_current_branch.return_value = "task/demo"
    flow_status = MagicMock(executor_session_id="sess-123")
    flow_service_cls.return_value.get_flow_status.return_value = flow_status

    session_id = load_session_id("executor")

    assert session_id == "sess-123"


@patch("vibe3.agents.session_service.FlowService")
def test_load_session_id_supports_manager_role_with_explicit_branch(
    flow_service_cls,
) -> None:
    flow_status = MagicMock(manager_session_id="sess-manager")
    flow_service_cls.return_value.get_flow_status.return_value = flow_status

    session_id = load_session_id("manager", branch="dev/issue-430")

    assert session_id == "sess-manager"
