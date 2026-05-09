"""Helper functions for GlobalDispatchCoordinator tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.global_dispatch_coordinator import GlobalDispatchCoordinator


def make_issue(number: int, priority: int = 5) -> MagicMock:
    """Create mock issue object."""
    issue = MagicMock()
    issue.number = number
    issue.labels = [f"priority/{priority}"]
    issue.milestone = None
    issue.assignees = ["manager-bot"]
    return issue


def make_issue_info(
    number: int,
    state: IssueState,
    *,
    assignees: list[str] | None = None,
    labels: list[str] | None = None,
) -> IssueInfo:
    """Create IssueInfo instance."""
    return IssueInfo(
        number=number,
        title=f"Issue {number}",
        state=state,
        labels=labels if labels is not None else [state.to_label()],
        assignees=assignees if assignees is not None else ["manager-bot"],
    )


def make_service(role: str, ready_issues: list) -> MagicMock:
    """Create mock orchestration service."""
    service = MagicMock()
    service.service_name = f"mock-{role}"
    role_map = {
        "manager": ("manager", "manager", "ready"),
        "handoff-manager": ("manager", "manager", "handoff"),
        "planner": ("plan", "planner", "claimed"),
        "plan": ("plan", "planner", "claimed"),
        "executor": ("run", "executor", "in-progress"),
        "run": ("run", "executor", "in-progress"),
        "reviewer": ("review", "reviewer", "review"),
        "review": ("review", "reviewer", "review"),
    }
    trigger_name, registry_role, trigger_state = role_map.get(
        role, ("manager", role, "ready")
    )
    service.role_def.trigger_name = trigger_name
    service.role_def.registry_role = registry_role
    service.role_def.trigger_state = IssueState(trigger_state)
    service.collect_ready_issues = AsyncMock(return_value=ready_issues)
    service._emit_dispatch_intent = MagicMock()
    service.config.manager_usernames = ["manager-bot"]
    service.config.supervisor_handoff.issue_label = "supervisor"
    service.config.repo = "owner/repo"
    service._github = MagicMock()
    return service


def make_capacity(remaining: int = 1) -> MagicMock:
    """Create mock capacity tracker."""
    capacity = MagicMock()
    capacity.config.max_concurrent_flows = max(remaining, 1)
    capacity.get_capacity_status = MagicMock(
        return_value={
            "remaining": remaining,
            "active_count": 0,
            "max_capacity": max(remaining, 1),
        }
    )
    capacity._run_command = MagicMock(
        side_effect=Exception("tmux not available in tests")
    )
    capacity._backend = None
    return capacity


def install_issue_loader(
    coordinator: GlobalDispatchCoordinator,
    states: dict[int, IssueState | None],
) -> None:
    """Install mock issue loader on coordinator."""
    coordinator._load_issue = lambda issue_number: (
        None
        if states.get(issue_number) is None
        else make_issue_info(issue_number, states[issue_number])
    )
