"""Execution-time gate policies shared by role services."""

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.role_contracts import CompletionContract
from vibe3.execution.roles import RoleDefinition
from vibe3.models.orchestration import IssueState
from vibe3.runtime.no_progress_policy import has_progress_changed
from vibe3.services.issue_failure_service import block_manager_noop_issue


def block_if_manager_noop(
    *,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    repo: str | None,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
) -> bool:
    """Enforce the manager MUST_CHANGE_LABEL completion contract."""
    current_state_label = before_snapshot.get("state_label", "")
    allow_close = current_state_label in ("state/ready", "state/handoff")
    if has_progress_changed(
        before_snapshot,
        after_snapshot,
        require_state_transition=True,
        allow_close_as_progress=allow_close,
    ):
        return False

    reason = "manager 本轮未产生状态迁移（must leave READY/HANDOFF per contract）"
    store.add_event(
        branch,
        "manager_noop_blocked",
        actor,
        detail=f"Manager auto-blocked issue #{issue_number}: {reason}",
        refs={"issue": str(issue_number), "reason": reason},
    )
    block_manager_noop_issue(
        issue_number=issue_number,
        repo=repo,
        reason=reason,
        actor=actor,
    )
    return True


def source_state_from_label(state_label: object) -> IssueState | None:
    """Map pre-run manager state label to issue state."""
    if state_label == "state/ready":
        return IssueState.READY
    if state_label == "state/handoff":
        return IssueState.HANDOFF
    return None


def apply_completion_gate(
    *,
    role: RoleDefinition,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    repo: str | None,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
) -> bool:
    """Apply the configured completion gate for a role.

    Returns True when the gate handled the completion and execution should stop.
    """
    if role.gate_config.completion_contract == CompletionContract.MUST_CHANGE_LABEL:
        return block_if_manager_noop(
            store=store,
            issue_number=issue_number,
            branch=branch,
            actor=actor,
            repo=repo,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )
    return False
