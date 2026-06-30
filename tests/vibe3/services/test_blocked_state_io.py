"""Tests for blocked_state_io module."""

from unittest.mock import MagicMock

from vibe3.models import IssueState
from vibe3.services.flow.blocked_state_io import BlockedStateIO


def test_write_database_cache_stores_reason(tmp_path):
    """write_database_cache should store blocked_reason and flow_status."""
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow.blocked_state_io import BlockedStateIO

    db = SQLiteClient(db_path=str(tmp_path / "test.db"))
    io = BlockedStateIO(store=db)

    # Write blocked state with a reason that needs cleaning
    io.write_database_cache(
        "test-branch",
        reason="codeagent-wrapper failed (code 1): Actual error message",
        blocked_by_issue=123,
        actor="test-actor",
    )

    # Verify blocked_reason and flow_status are stored
    flow = db.get_flow_state("test-branch")
    assert flow is not None
    assert (
        flow.get("blocked_reason")
        == "codeagent-wrapper failed (code 1): Actual error message"
    )
    assert flow.get("flow_status") == "blocked"


def test_clear_database_cache_resets_transition_count(tmp_path):
    """clear_database_cache should reset transition_count to 0."""
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow.blocked_state_io import BlockedStateIO

    db = SQLiteClient(db_path=str(tmp_path / "test.db"))

    # Create flow with non-zero transition_count
    db.update_flow_state(
        "test-branch",
        flow_status="blocked",
        blocked_reason="transition count exceeded",
        transition_count=15,
        latest_actor="system",
    )

    io = BlockedStateIO(store=db)
    io.clear_database_cache("test-branch", actor="human:resume")

    # Verify transition_count reset
    flow = db.get_flow_state("test-branch")
    assert flow is not None
    assert flow.get("transition_count") == 0, "transition_count should be reset to 0"
    assert flow.get("blocked_reason") is None
    assert flow.get("flow_status") == "active"


def test_clear_database_cache_returns_early_when_store_is_none():
    """clear_database_cache should return early when store is None."""
    from vibe3.services.flow.blocked_state_io import BlockedStateIO

    io = BlockedStateIO(store=None)
    # Should not raise any exception
    io.clear_database_cache("test-branch", actor="human:resume")


def test_clear_database_cache_handles_transition_history_exception(
    tmp_path, monkeypatch
):
    """clear_database_cache should handle exception from clear_transition_history."""
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow.blocked_state_io import BlockedStateIO

    db = SQLiteClient(db_path=str(tmp_path / "test.db"))

    # Create flow state
    db.update_flow_state(
        "test-branch",
        flow_status="blocked",
        blocked_reason="test",
        latest_actor="system",
    )

    # Mock clear_transition_history to raise exception
    def mock_clear_history(conn, branch):
        raise RuntimeError("Database error")

    monkeypatch.setattr(db, "clear_transition_history", mock_clear_history)

    io = BlockedStateIO(store=db)
    # Should not raise exception, just log warning
    io.clear_database_cache("test-branch", actor="human:resume")

    # Verify flow state was still updated (transition_count reset)
    flow = db.get_flow_state("test-branch")
    assert flow is not None
    assert flow.get("transition_count") == 0
    assert flow.get("flow_status") == "active"


def test_write_label_state_normalize_uses_strict_replacement() -> None:
    label_service = MagicMock()
    label_service.replace_issue_state.return_value = "normalized"
    io = BlockedStateIO(label_service=label_service)

    result = io.write_label_state(
        123,
        IssueState.IN_PROGRESS,
        actor="recovery:resume",
        normalize=True,
    )

    assert result == "normalized"
    label_service.replace_issue_state.assert_called_once_with(
        123,
        IssueState.IN_PROGRESS,
        actor="recovery:resume",
    )
    label_service.confirm_issue_state.assert_not_called()
