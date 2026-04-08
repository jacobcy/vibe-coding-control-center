from unittest.mock import MagicMock, patch

from vibe3.agents.session_service import load_session_id


def test_load_session_id_ignores_tmux_session_name() -> None:
    """Should ignore session IDs that look like tmux session names."""
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "executor", "backend_session_id": "vibe3-run-issue-451"}
    ]

    with (
        patch(
            "vibe3.agents.session_service.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/issue-451")
            ),
        ),
        patch(
            "vibe3.agents.session_service.SessionRegistryService",
            return_value=registry,
        ),
    ):
        session_id = load_session_id("executor")

    assert session_id is None


def test_load_session_id_returns_valid_backend_session_id() -> None:
    """Should return valid backend_session_id from registry."""
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "executor", "backend_session_id": "ses_2aea4d6b6ffexDUssWC9tEP4Nh"}
    ]

    with (
        patch(
            "vibe3.agents.session_service.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/issue-451")
            ),
        ),
        patch(
            "vibe3.agents.session_service.SessionRegistryService",
            return_value=registry,
        ),
    ):
        session_id = load_session_id("executor")

    assert session_id == "ses_2aea4d6b6ffexDUssWC9tEP4Nh"


def test_load_session_id_filters_by_role() -> None:
    """Should only return session matching the requested role."""
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "planner", "backend_session_id": "ses_planner123"},
        {"role": "executor", "backend_session_id": "ses_executor456"},
    ]

    with (
        patch(
            "vibe3.agents.session_service.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/issue-451")
            ),
        ),
        patch(
            "vibe3.agents.session_service.SessionRegistryService",
            return_value=registry,
        ),
    ):
        session_id = load_session_id("executor")

    assert session_id == "ses_executor456"


def test_load_session_id_returns_none_when_no_matching_role() -> None:
    """Should return None when no session matches the requested role."""
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "planner", "backend_session_id": "ses_planner123"},
    ]

    with (
        patch(
            "vibe3.agents.session_service.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/issue-451")
            ),
        ),
        patch(
            "vibe3.agents.session_service.SessionRegistryService",
            return_value=registry,
        ),
    ):
        session_id = load_session_id("executor")

    assert session_id is None


def test_load_session_id_returns_none_when_no_backend_session_id() -> None:
    """Should return None when session has no backend_session_id."""
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "executor", "backend_session_id": None}
    ]

    with (
        patch(
            "vibe3.agents.session_service.GitClient",
            return_value=MagicMock(
                get_current_branch=MagicMock(return_value="task/issue-451")
            ),
        ),
        patch(
            "vibe3.agents.session_service.SessionRegistryService",
            return_value=registry,
        ),
    ):
        session_id = load_session_id("executor")

    assert session_id is None
