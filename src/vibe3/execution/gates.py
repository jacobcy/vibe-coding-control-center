"""Execution-time gate policies shared by role services."""

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.role_contracts import CompletionContract
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


def apply_request_completion_gate(
    *,
    request: ExecutionRequest,
    store: SQLiteClient,
    repo: str | None,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
) -> bool:
    """Apply the completion gate declared on an ExecutionRequest.

    This is the unified entry point for post-sync gate checks.
    Returns True when the gate handled the completion and execution should stop.
    """
    gate = request.completion_gate
    if gate is None:
        return False
    if gate == CompletionContract.MUST_CHANGE_LABEL:
        return block_if_manager_noop(
            store=store,
            issue_number=request.target_id,
            branch=request.target_branch,
            actor=request.actor,
            repo=repo,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
        )
    return False
