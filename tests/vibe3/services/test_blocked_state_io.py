"""Tests for blocked_state_io module."""


def test_clear_database_cache_resets_transition_count(tmp_path):
    """clear_database_cache should reset transition_count to 0."""
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.blocked_state_io import BlockedStateIO

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
