"""Flow classification service."""

from enum import Enum

from vibe3.models.flow import FlowStatusResponse
from vibe3.services.status_query_service import is_auto_task_branch


class FlowCategory(str, Enum):
    """Flow classification by branch type and issue binding."""

    AUTO_TASK = "auto_task"  # task/issue-N or dev/issue-N (automated)
    ISSUE_BOUND = "issue_bound"  # Has issue binding but not auto-task pattern
    MANUAL = "manual"  # No issue binding, manual branch


class FlowState(str, Enum):
    """Flow execution state for display grouping."""

    ACTIVE = "active"  # Normal active flow
    BLOCKED = "blocked"  # Flow is blocked (blocked_by field set)
    DONE = "done"  # Flow completed
    ABORTED = "aborted"  # Flow aborted
    STALE = "stale"  # Flow marked as stale


def classify_flow(flow: FlowStatusResponse) -> FlowCategory:
    """Classify flow by branch pattern and issue binding.

    Auto-task branches: task/issue-N pattern (orchestra managed)
    Issue-bound branches: Manual branches with issue binding
    Manual branches: No issue binding

    Args:
        flow: Flow status response

    Returns:
        Flow category (AUTO_TASK, ISSUE_BOUND, or MANUAL)
    """
    # 1. Check if auto-task branch (task/issue-N only)
    if is_auto_task_branch(flow.branch):
        return FlowCategory.AUTO_TASK

    # 2. Check if has issue binding
    if flow.task_issue_number:
        return FlowCategory.ISSUE_BOUND

    # 3. Manual branch (no issue binding)
    return FlowCategory.MANUAL


def get_flow_state(flow: FlowStatusResponse) -> FlowState:
    """Get flow execution state for grouping.

    Args:
        flow: Flow status response

    Returns:
        Flow state for display grouping
    """
    # Map flow_status to FlowState
    status_to_state = {
        "active": FlowState.ACTIVE,
        "blocked": FlowState.BLOCKED,
        "done": FlowState.DONE,
        "aborted": FlowState.ABORTED,
        "stale": FlowState.STALE,
    }

    flow_status = flow.flow_status or "active"
    return status_to_state.get(flow_status, FlowState.ACTIVE)
