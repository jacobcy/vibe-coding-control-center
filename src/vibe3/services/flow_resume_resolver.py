"""Flow resume resolver service.

Provides pure logic to infer the correct GitHub state label for a flow based
on its local reference states (pr_ref, audit_ref, plan_ref, report_ref).
"""

from vibe3.models.flow import FlowState
from vibe3.models.orchestration import IssueState


def infer_resume_label(flow_state: FlowState) -> IssueState:
    """Infer the correct state label a flow should return to.

    Used by:
    1. Qualify gate automatic unblock (determining target label)
    2. `vibe3 task resume --label` (without explicit value)

    Priority Rules (High to Low):
    1. pr_ref exists -> HANDOFF (Code is ready for delivery)
    2. audit_ref exists -> IN_PROGRESS or HANDOFF (Based on verdict)
    3. report_ref exists -> REVIEW (Code is written, needs review)
    4. plan_ref exists -> IN_PROGRESS (Plan exists, needs execution)
    5. default -> CLAIMED (Start fresh)

    Args:
        flow_state: The current local state of the flow

    Returns:
        The inferred target IssueState
    """
    if flow_state.pr_ref:
        # PR already exists -> Manager should take over
        return IssueState.HANDOFF

    if flow_state.audit_ref and flow_state.latest_verdict:
        verdict = flow_state.latest_verdict.verdict.lower()
        # Review has been completed
        if verdict in {"pass", "major", "minor"}:
            return IssueState.IN_PROGRESS  # Need to modify code based on review
        if verdict == "unknown":
            return IssueState.HANDOFF  # Cannot decide -> Manager takes over

    if flow_state.plan_ref and flow_state.report_ref:
        # Code has been written (report exists) but no review yet
        return IssueState.REVIEW

    if flow_state.plan_ref:
        # Plan exists but no code (report) yet
        return IssueState.IN_PROGRESS

    # Everything is missing -> Need to start from the beginning
    return IssueState.CLAIMED
