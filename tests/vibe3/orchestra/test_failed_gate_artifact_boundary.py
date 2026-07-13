"""Regression: FailedGate stays separate from artifact-blocked state (FR-013).

Boundary locked by spec 012 US2:
- FailedGate (domain/failed_gate.py): global freeze on persistent RUNTIME /
  SYSTEM errors (E_MODEL_* immediate; E_API_* threshold). Survives restarts.
- artifact blocker (services/flow/recovery.py ARTIFACT_BLOCKED): a recorded
  artifact file that later disappeared. The scene stays blocked for repair;
  it is NEVER rebuilt and NEVER activates FailedGate.

Artifact disappearance is a repair blocker, not a runtime/system error — the
two failure modes ride separate rails and must not trigger each other.
Spec 012 US2, FR-013, SC-002.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.domain.failed_gate import FailedGate
from vibe3.services.flow.recovery import FlowRecoveryService, RecoveryAction
from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService


@pytest.fixture(autouse=True)
def reset_error_tracking() -> Iterator[None]:
    yield
    db_paths = list(ErrorTrackingService._registry.keys())
    ErrorTrackingService.clear_instance()
    for db_path in db_paths:
        try:
            with sqlite3.connect(db_path) as conn:
                conn.execute("DELETE FROM error_log")
                conn.execute(
                    "UPDATE failed_gate_state SET is_active = 0, "
                    "reason = NULL, triggered_at = NULL, blocked_ticks = 0 "
                    "WHERE id = 1"
                )
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e):
                raise


@pytest.fixture
def temp_store(tmp_path: Path) -> SQLiteClient:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from vibe3.clients.sqlite_schema import init_schema

    init_schema(conn)
    conn.close()
    return SQLiteClient(db_path=str(db_path))


def test_artifact_blocker_does_not_activate_failed_gate(
    temp_store: SQLiteClient,
) -> None:
    """FR-013: MISSING_ARTIFACT recovery (auto path) returns ARTIFACT_BLOCKED
    with success=False but NEVER writes to error_log or activates FailedGate.
    Artifact disappearance is a repair blocker, not a system error — the gate
    stays open (spec 012 US2, SC-002)."""
    ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )
    # Record a healthy worktree flow whose plan_ref file has disappeared.
    temp_store.update_flow_state(
        "task/issue-42",
        worktree_path="/wt/task/issue-42",
        plan_ref="docs/plans/missing.md",
    )
    git = MagicMock()
    git.find_worktree_path_for_branch.return_value = Path("/wt/task/issue-42")
    git.branch_exists.return_value = True
    github = MagicMock()
    svc = FlowRecoveryService(store=temp_store, git_client=git, github_client=github)

    with patch(
        "vibe3.services.flow.consistency.check_ref_exists",
        return_value=("docs/plans/missing.md", False),
    ):
        result = svc.recover_auto(
            branch="task/issue-42",
            issue_number=42,
            reason="health check",
        )

    assert result.action == RecoveryAction.ARTIFACT_BLOCKED
    assert not result.success
    # No error_log entry was written → gate stays OPEN.
    assert not FailedGate(store=temp_store).check().blocked


def test_runtime_model_error_still_routes_through_failed_gate(
    temp_store: SQLiteClient,
) -> None:
    """FR-013 contrast: a runtime E_MODEL_* error still activates FailedGate
    immediately. This rail is unaffected by ARTIFACT_BLOCKED — runtime/system
    errors and artifact losses stay on separate paths."""
    ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )
    ErrorTrackingService.get_instance(store=temp_store).record_error(
        "E_MODEL_NOT_FOUND", "Model not found"
    )
    assert FailedGate(store=temp_store).check().blocked
