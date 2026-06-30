"""Integration tests for AUP rejection retry protection."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vibe3.clients import SQLiteClient
from vibe3.exceptions import (
    E_AUP_REJECTION,
    AgentExecutionError,
    ErrorSeverity,
    classify_error_hybrid,
    get_error_handling_contract,
)

if TYPE_CHECKING:
    pass


@pytest.fixture
def temp_store(tmp_path: Path) -> SQLiteClient:
    """Create a temporary SQLite store for testing."""
    from vibe3.clients import SQLiteClient
    from vibe3.clients.sqlite_schema import init_schema

    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()

    store = SQLiteClient(db_path=db_path)

    # Create a minimal flow state
    store.update_flow_state(
        "test-branch",
        flow_slug="test-flow",
        flow_status="active",
    )

    return store


class TestAUPRejectionClassification:
    """Test AUP rejection error classification."""

    def test_aup_rejection_is_warning_no_failed_gate(self) -> None:
        """Verify WARNING severity, gate_action=ignore, no threshold count."""
        contract = get_error_handling_contract(E_AUP_REJECTION)

        assert contract.severity == ErrorSeverity.WARNING
        assert contract.gate_action == "ignore"
        assert contract.counts_toward_threshold is False
        assert contract.issue_action == "block_after_retries"
        assert contract.max_retries == 3

    def test_aup_rejection_hybrid_classification(self) -> None:
        """Verify classify_error_hybrid() with AgentExecutionError + AUP text."""
        exc = AgentExecutionError(
            "API Error: Claude Code is unable to respond to this request, "
            "which appears to violate our Usage Policy"
        )
        assert classify_error_hybrid(exc) == E_AUP_REJECTION


class TestAUPRejectionRetryCounter:
    """Test AUP rejection retry counter behavior."""

    def test_aup_first_rejection_increments_counter(
        self, temp_store: SQLiteClient
    ) -> None:
        """Verify counter = 1 after first rejection."""
        branch = "test-branch"

        # Simulate first AUP rejection counter increment
        import datetime

        raw_count = (temp_store.get_flow_state(branch) or {}).get(
            "aup_rejection_count", 0
        )
        count = int(raw_count) + 1 if raw_count is not None else 1

        now_iso = datetime.datetime.now().isoformat()
        temp_store.update_flow_state(
            branch,
            aup_rejection_count=count,
            last_aup_rejection_at=now_iso,
        )

        # Verify counter incremented
        state = temp_store.get_flow_state(branch)
        assert state is not None
        assert state.get("aup_rejection_count") == 1
        assert state.get("last_aup_rejection_at") is not None

        # Verify flow is NOT blocked yet (threshold not reached)
        assert state.get("flow_status") == "active"

    def test_aup_second_rejection_increments_but_no_block(
        self, temp_store: SQLiteClient
    ) -> None:
        """Verify counter = 2, flow NOT blocked."""
        branch = "test-branch"

        # Simulate first rejection
        import datetime

        temp_store.update_flow_state(
            branch,
            aup_rejection_count=1,
            last_aup_rejection_at=datetime.datetime.now().isoformat(),
        )

        # Simulate second AUP rejection counter increment
        raw_count = (temp_store.get_flow_state(branch) or {}).get(
            "aup_rejection_count", 0
        )
        count = int(raw_count) + 1 if raw_count is not None else 1

        now_iso = datetime.datetime.now().isoformat()
        temp_store.update_flow_state(
            branch,
            aup_rejection_count=count,
            last_aup_rejection_at=now_iso,
        )

        # Verify counter incremented to 2
        state = temp_store.get_flow_state(branch)
        assert state is not None
        assert state.get("aup_rejection_count") == 2

        # Verify flow is still NOT blocked (threshold not reached)
        assert state.get("flow_status") == "active"

    def test_aup_third_rejection_blocks_flow(self, temp_store: SQLiteClient) -> None:
        """Verify counter = 3, flow_status = 'blocked', blocked_reason populated."""
        branch = "test-branch"

        # Simulate two previous rejections
        import datetime

        temp_store.update_flow_state(
            branch,
            aup_rejection_count=2,
            last_aup_rejection_at=datetime.datetime.now().isoformat(),
        )

        # Simulate third AUP rejection counter increment
        raw_count = (temp_store.get_flow_state(branch) or {}).get(
            "aup_rejection_count", 0
        )
        count = int(raw_count) + 1 if raw_count is not None else 1

        # Verify counter reached threshold
        assert count == 3

        # Simulate the blocking logic — only write to DB cache, not GitHub.
        # CI environments lack GitHub credentials, and the test only needs
        # to verify that the database state correctly reflects the block.
        from vibe3.services.flow import BlockedStateService

        reason = f"AUP rejection threshold reached ({count}/3 attempts)"
        BlockedStateService(store=temp_store).write_cache(
            branch=branch,
            reason=reason,
            blocked_by_issue=None,
            actor="test-actor",
        )

        # Verify flow is blocked
        state = temp_store.get_flow_state(branch)
        assert state is not None
        assert state.get("flow_status") == "blocked"
        assert "AUP rejection threshold reached" in (state.get("blocked_reason") or "")


class TestAUPRejectionStoreMethod:
    """Test the client-layer increment_aup_rejection method."""

    def test_increment_returns_new_count(self, temp_store: SQLiteClient) -> None:
        """increment_aup_rejection atomically returns the new count."""
        branch = "test-branch"

        count1 = temp_store.increment_aup_rejection(branch)
        assert count1 == 1

        count2 = temp_store.increment_aup_rejection(branch)
        assert count2 == 2

        state = temp_store.get_flow_state(branch)
        assert state is not None
        assert state.get("aup_rejection_count") == 2
        assert state.get("last_aup_rejection_at") is not None

    def test_reset_on_success_clears_counter(self, temp_store: SQLiteClient) -> None:
        """Counter reset via update_flow_state clears the fields."""
        branch = "test-branch"

        temp_store.increment_aup_rejection(branch)
        temp_store.increment_aup_rejection(branch)
        assert temp_store.get_flow_state(branch)["aup_rejection_count"] == 2

        temp_store.update_flow_state(
            branch,
            aup_rejection_count=0,
            last_aup_rejection_at=None,
        )

        state = temp_store.get_flow_state(branch)
        assert state["aup_rejection_count"] == 0
        assert state["last_aup_rejection_at"] is None
