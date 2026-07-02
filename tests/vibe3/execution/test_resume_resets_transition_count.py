"""End-to-end tests: blocked resume preserves transition evidence.

This test verifies the fix for issue #1880:
- Flow gets blocked by single-step limit (3 occurrences)
- task resume clears blocked_reason and records blocked -> inferred state
- existing transition evidence remains in the current epoch
"""

import sqlite3
from unittest.mock import MagicMock

from vibe3.clients import SQLiteClient
from vibe3.models import IssueState
from vibe3.services.flow import BlockedStateService


def test_resume_preserves_history_and_records_recovery(tmp_path):
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
    label_service.get_state.return_value = IssueState.BLOCKED
    label_service.replace_issue_state.return_value = "normalized"

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

    # Existing evidence remains and the real blocked -> ready transition is added.
    flow = db.get_flow_state(branch)
    assert flow is not None
    assert flow.get("transition_count") == 6

    # Verify transition_history cleared
    with sqlite3.connect(db.db_path) as conn:
        count_after = db.count_specific_pair(
            conn, branch, "state/claimed", "state/handoff"
        )
    assert count_after == 3
    with sqlite3.connect(db.db_path) as conn:
        assert db.count_specific_pair(conn, branch, "state/blocked", "state/ready") == 1


def test_resume_retains_block_when_transition_budget_is_exhausted(tmp_path):
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
    label_service.get_state.return_value = IssueState.BLOCKED

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

    assert result is None

    # The failed recovery attempt does not erase evidence or mutate the label.
    flow = db.get_flow_state(branch)
    assert flow.get("transition_count") == 20
    assert flow.get("flow_status") == "blocked"
    label_service.replace_issue_state.assert_not_called()

    # Verify transition_history cleared
    with sqlite3.connect(db.db_path) as conn:
        count_after = db.count_specific_pair(
            conn, branch, "state/claimed", "state/handoff"
        )
    assert count_after == 3
