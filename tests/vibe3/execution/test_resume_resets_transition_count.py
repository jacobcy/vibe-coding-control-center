"""End-to-end test: flow resume should reset transition counters.

This test verifies the fix for issue #1880:
- Flow gets blocked by single-step limit (3 occurrences)
- task resume clears blocked_reason AND resets counters
- Flow can continue without immediate re-blocking
"""

import sqlite3
from unittest.mock import MagicMock, patch

from vibe3.clients import SQLiteClient
from vibe3.execution.noop_gate import apply_unified_noop_gate
from vibe3.models import IssueState
from vibe3.services.flow import BlockedStateService


def test_resume_resets_single_step_limit_counter(tmp_path):
    """Flow blocked by single-step limit should resume successfully."""
    db = SQLiteClient(db_path=str(tmp_path / "test.db"))

    branch = "test-branch"
    issue_number = 123

    # Setup: Create flow state
    db.update_flow_state(
        branch,
        flow_status="active",
        transition_count=5,
        latest_actor="test",
    )

    # Simulate 3 occurrences of same transition pair
    with sqlite3.connect(db.db_path) as conn:
        db.record_transition(conn, branch, "state/claimed", "state/handoff", "actor")
        db.record_transition(conn, branch, "state/claimed", "state/handoff", "actor")
        db.record_transition(conn, branch, "state/claimed", "state/handoff", "actor")

    # Verify 3 occurrences recorded
    with sqlite3.connect(db.db_path) as conn:
        count = db.count_specific_pair(conn, branch, "state/claimed", "state/handoff")
    assert count == 3

    # Mock GitHub client
    github_client = MagicMock()
    github_client.get_issue_labels.return_value = [
        {"name": "state/blocked"},
        {"name": "priority/8"},
    ]
    github_client.get_issue_body.return_value = ""
    github_client.update_issue_labels.return_value = True
    github_client.update_issue_body.return_value = True

    # Mock label service
    label_service = MagicMock()
    label_service.confirm_issue_state.return_value = "advanced"

    # Resume: clear blocked state
    service = BlockedStateService(
        github_client=github_client,
        label_service=label_service,
        store=db,
    )
    result = service.reconcile_blocked(
        issue_number=issue_number,
        branch=branch,
        clear_reason=True,
        actor="human:resume",
    )

    assert result is not None, "Should return target state (unblocked)"
    assert result == IssueState.READY, "Should return READY as target state"

    # Verify transition_count reset
    flow = db.get_flow_state(branch)
    assert flow is not None
    assert flow.get("transition_count") == 0, "transition_count should be reset"

    # Verify transition_history cleared
    with sqlite3.connect(db.db_path) as conn:
        count_after = db.count_specific_pair(
            conn, branch, "state/claimed", "state/handoff"
        )
    assert count_after == 0, "transition_history should be cleared"

    # Verify flow can transition again without blocking
    # (Simulate one more transition - should not block)
    mock_block_fn = MagicMock()
    with patch(
        "vibe3.execution.noop_gate.get_role_block_function",
        return_value=mock_block_fn,
    ):
        with patch(
            "vibe3.execution.state_verification.StateVerificationService.get_issue_state_labels"
        ) as mock_state:
            mock_state.return_value = (frozenset({"state/handoff"}), False)

            apply_unified_noop_gate(
                store=db,
                issue_number=issue_number,
                branch=branch,
                actor="test",
                role="executor",
                before_state_label="state/claimed",
                repo="test/repo",
                flow_state=flow,
            )

    # Should NOT have called block function (no re-blocking)
    mock_block_fn.assert_not_called()


def test_resume_resets_hard_limit_counter(tmp_path):
    """Flow blocked by hard limit (20 transitions) should resume successfully."""
    db = SQLiteClient(db_path=str(tmp_path / "test.db"))

    branch = "test-branch"
    issue_number = 456

    # Setup: Create flow state at hard limit
    db.update_flow_state(
        branch,
        flow_status="blocked",
        blocked_reason="transition count exceeded hard limit",
        transition_count=20,
        latest_actor="system",
    )

    # Simulate transition history
    with sqlite3.connect(db.db_path) as conn:
        db.record_transition(conn, branch, "state/claimed", "state/handoff", "actor")
        db.record_transition(conn, branch, "state/claimed", "state/handoff", "actor")
        db.record_transition(conn, branch, "state/claimed", "state/handoff", "actor")

    # Verify transition history recorded
    with sqlite3.connect(db.db_path) as conn:
        count = db.count_specific_pair(conn, branch, "state/claimed", "state/handoff")
    assert count == 3

    # Mock GitHub client
    github_client = MagicMock()
    github_client.get_issue_labels.return_value = [{"name": "state/blocked"}]
    github_client.get_issue_body.return_value = ""
    github_client.update_issue_labels.return_value = True
    github_client.update_issue_body.return_value = True

    # Mock label service
    label_service = MagicMock()
    label_service.confirm_issue_state.return_value = "advanced"

    # Resume
    service = BlockedStateService(
        github_client=github_client,
        label_service=label_service,
        store=db,
    )
    result = service.reconcile_blocked(
        issue_number=issue_number,
        branch=branch,
        clear_reason=True,
        actor="human:resume",
    )

    assert result is not None, "Should return target state (unblocked)"

    # Verify counter reset
    flow = db.get_flow_state(branch)
    assert flow.get("transition_count") == 0, "Hard limit counter should be reset"
    assert flow.get("blocked_reason") is None
    assert flow.get("flow_status") == "active"

    # Verify transition_history cleared
    with sqlite3.connect(db.db_path) as conn:
        count_after = db.count_specific_pair(
            conn, branch, "state/claimed", "state/handoff"
        )
    assert count_after == 0, "transition_history should be cleared"

    # Verify flow can transition again without blocking
    mock_block_fn = MagicMock()
    with patch(
        "vibe3.execution.noop_gate.get_role_block_function",
        return_value=mock_block_fn,
    ):
        with patch(
            "vibe3.execution.state_verification.StateVerificationService.get_issue_state_labels"
        ) as mock_state:
            mock_state.return_value = (frozenset({"state/handoff"}), False)

            apply_unified_noop_gate(
                store=db,
                issue_number=issue_number,
                branch=branch,
                actor="test",
                role="executor",
                before_state_label="state/claimed",
                repo="test/repo",
                flow_state=flow,
            )

    # Should NOT have called block function (no re-blocking)
    mock_block_fn.assert_not_called()
