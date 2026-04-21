"""Role registry aggregating all dispatchable roles."""

from __future__ import annotations

from vibe3.domain.events import (
    ExecutorDispatchIntent,
    ManagerDispatchIntent,
    PlannerDispatchIntent,
    ReviewerDispatchIntent,
)
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.roles.manager import HANDOFF_MANAGER_ROLE, MANAGER_ROLE
from vibe3.roles.plan import (
    PLANNER_ROLE,
)
from vibe3.roles.review import (
    REVIEWER_ROLE,
)
from vibe3.roles.run import (
    EXECUTOR_ROLE,
)

LABEL_DISPATCH_ROLES: tuple[TriggerableRoleDefinition, ...] = (
    MANAGER_ROLE,
    HANDOFF_MANAGER_ROLE,
    PLANNER_ROLE,
    EXECUTOR_ROLE,
    REVIEWER_ROLE,
)


def build_label_dispatch_event(
    role: TriggerableRoleDefinition,
    issue: IssueInfo,
    *,
    branch: str,
) -> (
    ManagerDispatchIntent
    | PlannerDispatchIntent
    | ExecutorDispatchIntent
    | ReviewerDispatchIntent
):
    """Build the authoritative domain event for a label-triggered role.

    Dispatch layer emits neutral intents only -- no execution-specific
    context (refs, commit_mode) is read here.  The handler layer enriches
    the request before calling the role builder.
    """
    trigger = role.trigger_name
    if trigger == "manager":
        return ManagerDispatchIntent(
            issue_number=issue.number,
            branch=branch,
            trigger_state=role.trigger_state.value,
            issue_title=issue.title if issue.title else None,
        )
    if trigger == "plan":
        return PlannerDispatchIntent(
            issue_number=issue.number,
            branch=branch,
            trigger_state=IssueState.CLAIMED.value,
        )
    if trigger == "run":
        return ExecutorDispatchIntent(
            issue_number=issue.number,
            branch=branch,
            trigger_state=IssueState.IN_PROGRESS.value,
        )
    if trigger == "review":
        return ReviewerDispatchIntent(
            issue_number=issue.number,
            branch=branch,
            trigger_state=IssueState.REVIEW.value,
        )
    raise ValueError(f"Unsupported label dispatch trigger: {trigger}")
