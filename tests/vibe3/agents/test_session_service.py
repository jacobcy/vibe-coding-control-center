from unittest.mock import MagicMock, patch

from vibe3.agents.session_service import load_session_id


def test_load_session_id_ignores_non_uuid_value() -> None:
    flow_status = MagicMock(executor_session_id="vibe3-run-issue-451")

    with (
        patch(
            "vibe3.agents.session_service.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/issue-451")
            ),
        ),
        patch(
            "vibe3.agents.session_service.FlowService",
            return_value=MagicMock(get_flow_status=MagicMock(return_value=flow_status)),
        ),
    ):
        session_id = load_session_id("executor")

    assert session_id is None


def test_load_session_id_returns_uuid_value() -> None:
    flow_status = MagicMock(executor_session_id="ses_2aea4d6b6ffexDUssWC9tEP4Nh")

    with (
        patch(
            "vibe3.agents.session_service.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/issue-451")
            ),
        ),
        patch(
            "vibe3.agents.session_service.FlowService",
            return_value=MagicMock(get_flow_status=MagicMock(return_value=flow_status)),
        ),
    ):
        session_id = load_session_id("executor")

    assert session_id == "ses_2aea4d6b6ffexDUssWC9tEP4Nh"
