"""Tests for shared agent execution service."""

from unittest.mock import MagicMock, patch

from vibe3.execution.session_service import load_session_id


@patch("vibe3.execution.session_service.SessionRegistryService")
@patch("vibe3.execution.session_service.GitClient")
def test_load_session_id_returns_registry_session(git_cls, registry_cls) -> None:
    """load_session_id should return session from registry."""
    git_cls.return_value.get_current_branch.return_value = "task/demo"
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "executor", "backend_session_id": "sess-123"}
    ]
    registry_cls.return_value = registry

    session_id = load_session_id("executor")

    assert session_id == "sess-123"


@patch("vibe3.execution.session_service.SessionRegistryService")
def test_load_session_id_supports_manager_role_with_explicit_branch(
    registry_cls,
) -> None:
    """load_session_id should return manager session from registry."""
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "manager", "backend_session_id": "sess-manager"}
    ]
    registry_cls.return_value = registry

    session_id = load_session_id("manager", branch="dev/issue-430")

    assert session_id == "sess-manager"


@patch("vibe3.execution.session_service.SessionRegistryService")
@patch("vibe3.execution.session_service.GitClient")
def test_load_session_id_returns_none_when_no_matching_role(
    git_cls, registry_cls
) -> None:
    """load_session_id should return None when no session matches role."""
    git_cls.return_value.get_current_branch.return_value = "task/demo"
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "planner", "backend_session_id": "sess-123"}
    ]
    registry_cls.return_value = registry

    session_id = load_session_id("executor")

    assert session_id is None


@patch("vibe3.execution.session_service.SessionRegistryService")
@patch("vibe3.execution.session_service.GitClient")
def test_load_session_id_ignores_tmux_session_names(git_cls, registry_cls) -> None:
    """load_session_id should ignore session IDs that look like tmux names."""
    git_cls.return_value.get_current_branch.return_value = "task/demo"
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "executor", "backend_session_id": "vibe3-run-issue-451"}
    ]
    registry_cls.return_value = registry

    session_id = load_session_id("executor")

    # vibe3-* session IDs are tmux names, not valid wrapper sessions
    assert session_id is None


@patch("vibe3.execution.session_service.SQLiteClient")
@patch("vibe3.execution.session_service.SessionRegistryService")
@patch("vibe3.execution.session_service.GitClient")
def test_load_session_id_returns_completed_session_backend_id(
    git_cls, registry_cls, store_cls
) -> None:
    """load_session_id should return backend_session_id from completed session."""
    git_cls.return_value.get_current_branch.return_value = "task/issue-700"
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = []
    registry_cls.return_value = registry

    store = MagicMock()
    store.get_latest_session_with_backend_id.return_value = {
        "id": 1,
        "role": "executor",
        "branch": "task/issue-700",
        "status": "done",
        "backend_session_id": "completed-session-id",
    }
    store_cls.return_value = store

    session_id = load_session_id("executor")

    assert session_id == "completed-session-id"
    store.get_latest_session_with_backend_id.assert_called_once_with(
        branch="task/issue-700", role="executor"
    )


@patch("vibe3.execution.session_service.SQLiteClient")
@patch("vibe3.execution.session_service.SessionRegistryService")
@patch("vibe3.execution.session_service.GitClient")
def test_load_session_id_prefers_live_over_completed(
    git_cls, registry_cls, store_cls
) -> None:
    """load_session_id should prefer live session over completed session."""
    git_cls.return_value.get_current_branch.return_value = "task/issue-701"
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = [
        {"role": "executor", "backend_session_id": "live-session-id"}
    ]
    registry_cls.return_value = registry

    store = MagicMock()
    store.get_latest_session_with_backend_id.return_value = {
        "id": 2,
        "role": "executor",
        "branch": "task/issue-701",
        "status": "done",
        "backend_session_id": "completed-session-id",
    }
    store_cls.return_value = store

    session_id = load_session_id("executor")

    assert session_id == "live-session-id"
    store.get_latest_session_with_backend_id.assert_not_called()


@patch("vibe3.execution.session_service.SQLiteClient")
@patch("vibe3.execution.session_service.SessionRegistryService")
@patch("vibe3.execution.session_service.GitClient")
def test_load_session_id_fallback_ignores_invalid_session_ids(
    git_cls, registry_cls, store_cls
) -> None:
    """load_session_id should ignore invalid session IDs in fallback."""
    git_cls.return_value.get_current_branch.return_value = "task/issue-702"
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = []
    registry_cls.return_value = registry

    store = MagicMock()
    store.get_latest_session_with_backend_id.return_value = {
        "id": 3,
        "role": "executor",
        "branch": "task/issue-702",
        "status": "done",
        "backend_session_id": "vibe3-run-issue-702",  # tmux-style, invalid
    }
    store_cls.return_value = store

    session_id = load_session_id("executor")

    assert session_id is None


@patch("vibe3.execution.session_service.SQLiteClient")
@patch("vibe3.execution.session_service.SessionRegistryService")
@patch("vibe3.execution.session_service.GitClient")
def test_load_session_id_fallback_ignores_aborted_with_no_backend_id(
    git_cls, registry_cls, store_cls
) -> None:
    """load_session_id should return None when aborted session has no backend_id."""
    git_cls.return_value.get_current_branch.return_value = "task/issue-703"
    registry = MagicMock()
    registry.get_truly_live_sessions_for_branch.return_value = []
    registry_cls.return_value = registry

    store = MagicMock()
    store.get_latest_session_with_backend_id.return_value = None
    store_cls.return_value = store

    session_id = load_session_id("executor")

    assert session_id is None
