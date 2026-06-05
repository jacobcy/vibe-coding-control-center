"""Label utilities and services for vibe3.

This module combines label utility functions and the LabelService class
for managing GitHub issue labels and state transitions.
"""

from __future__ import annotations

import functools
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from loguru import logger

from vibe3.clients.github_labels import GhIssueLabelPort, IssueLabelPort
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.state_machine import (
    STATE_LABEL_META,
    VIBE_TASK_LABEL,
    validate_transition,
)
from vibe3.exceptions import InvalidTransitionError, SystemError
from vibe3.models import IssueState
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import StateTransition

if TYPE_CHECKING:
    from vibe3.models import IssueInfo
    from vibe3.roles import TriggerableRoleDefinition


# ============================================================================
# Label Utility Functions
# ============================================================================


def normalize_labels(raw_labels: object) -> list[str]:
    """Extract label names from GitHub issue payload labels field."""
    if not isinstance(raw_labels, list):
        return []
    result: list[str] = []
    for item in raw_labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                result.append(name)
    return result


def normalize_assignees(raw_assignees: object) -> list[str]:
    """Extract assignee logins from GitHub issue payload assignees field."""
    if not isinstance(raw_assignees, list):
        return []
    assignees: list[str] = []
    for item in raw_assignees:
        if isinstance(item, dict):
            login = item.get("login")
            if isinstance(login, str) and login:
                assignees.append(login)
    return assignees


def has_manager_assignee(
    assignees: list[str],
    manager_usernames: list[str] | tuple[str, ...],
) -> bool:
    """Whether issue assignees still include a configured manager username.

    Returns True if manager_usernames is empty (no restriction configured).
    This prevents all issues from being filtered out when no managers are configured.
    """
    if not manager_usernames:
        return True  # No restriction: all issues allowed
    return any(assignee in manager_usernames for assignee in assignees)


@functools.lru_cache(maxsize=8)
def _make_dispatch_policy(
    supervisor_label: str,
    manager_usernames: tuple[str, ...],
) -> "object":
    from vibe3.services.issue_dispatch_policy import IssueDispatchPolicy

    return IssueDispatchPolicy(
        supervisor_label=supervisor_label,
        manager_usernames=manager_usernames,
    )


def should_skip_from_queue(
    issue: IssueInfo,
    *,
    supervisor_label: str,
    manager_usernames: list[str] | tuple[str, ...],
    require_manager_assignee: bool = True,
) -> bool:
    """Check whether an issue should be skipped from dispatch queue.

    Issues are skipped if:
    1. They have the supervisor label (managed by supervisor, not auto-dispatch)
    2. They don't have a manager assignee (when required for this queue stage)
    3. They are roadmap/rfc (human discussion, not ready for execution)
    4. They are roadmap/epic (scope too large, needs decomposition)

    Args:
        issue: Issue information
        supervisor_label: Label name for supervisor issues (from config)
        manager_usernames: List of manager usernames (from config)
        require_manager_assignee: Whether this queue stage still requires the
            issue to be assigned to a manager username. Entry-point ready issues
            do; downstream state-label dispatch does not.

    Returns:
        True if issue should be skipped, False otherwise
    """
    from vibe3.services.issue_dispatch_policy import IssueDispatchPolicy

    policy: IssueDispatchPolicy = _make_dispatch_policy(  # type: ignore[assignment]
        supervisor_label, tuple(manager_usernames)
    )
    reasons = policy.exclusion_reasons(issue)
    if require_manager_assignee:
        return bool(reasons)

    # Keep the legacy "skip" behavior for non-assignee exclusions only.
    assignee_only_codes = {"missing_manager_assignee", "non_manager_assignee"}
    return any(reason.code not in assignee_only_codes for reason in reasons)


def clean_old_state_labels(
    issue: "IssueInfo",
    role: "TriggerableRoleDefinition",
    config: OrchestraConfig,
) -> None:
    """Remove conflicting state/* labels before dispatch.

    Args:
        issue: Issue to clean labels for
        role: Role definition for this dispatch
        config: Orchestra configuration
    """
    old_state_labels = [
        lb
        for lb in issue.labels
        if lb.startswith("state/") and lb != role.trigger_state.to_label()
    ]
    if old_state_labels:
        try:
            label_port = GhIssueLabelPort(repo=config.repo)
            for old_lb in old_state_labels:
                label_port.remove_issue_label(issue.number, old_lb)
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to clean old state labels for #{issue.number}: {exc}"
            )


# ============================================================================
# Label Service
# ============================================================================


class LabelService:
    """Coordinate issue state transitions against GitHub labels."""

    def __init__(
        self,
        issue_port: IssueLabelPort | None = None,
        repo: str | None = None,
    ) -> None:
        if issue_port is None and repo is None:
            repo = load_orchestra_config().repo
        self.issue_port = issue_port or GhIssueLabelPort(repo=repo)

    def get_state(self, issue_number: int) -> IssueState | None:
        """Get current orchestration state of an issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            IssueState: Current state
            None: No state/* label found
        """
        logger.bind(
            external="github",
            operation="get_state",
            issue_number=issue_number,
        ).debug("Getting issue state")

        labels = self.issue_port.get_issue_labels(issue_number)
        if labels is None:
            logger.bind(external="github", issue_number=issue_number).warning(
                "Failed to get issue labels"
            )
            return None

        for name in labels:
            state = IssueState.from_label(name)
            if state:
                return state

        return None

    def transition(
        self,
        issue_number: int,
        to_state: IssueState,
        actor: str,
        force: bool = False,
    ) -> StateTransition:
        """Execute state transition.

        Args:
            issue_number: GitHub issue number
            to_state: Target state
            actor: Actor identifier (e.g., "flow:blocked", "agent:run")
            force: Skip transition rule validation

        Returns:
            StateTransition: Transition record

        Raises:
            InvalidTransitionError: Invalid transition and not forced
        """
        from_state = self.get_state(issue_number)

        # Validate transition
        validate_transition(from_state, to_state, force=force)

        # Execute transition
        self.set_state(issue_number, to_state)

        logger.bind(
            external="github",
            operation="transition",
            issue_number=issue_number,
            from_state=from_state.value if from_state else None,
            to_state=to_state.value,
            actor=actor,
        ).info("State transition completed")

        return StateTransition(
            issue_number=issue_number,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            timestamp=datetime.now(),
            forced=force,
        )

    def confirm_issue_state(
        self,
        issue_number: int,
        to_state: IssueState,
        actor: str,
        force: bool = False,
    ) -> Literal["confirmed", "advanced", "blocked"]:
        """Confirm target issue state with minimum action."""
        current_state = self.get_state(issue_number)
        if current_state == to_state:
            return "confirmed"
        try:
            self.transition(issue_number, to_state, actor=actor, force=force)
        except (InvalidTransitionError, SystemError):
            return "blocked"
        return "advanced"

    def set_state(self, issue_number: int, state: IssueState) -> None:
        """Directly set state (internal method, atomically replace state/* labels).

        Args:
            issue_number: GitHub issue number
            state: Target state
        """
        self._ensure_state_label_exists(state)

        # Get current state labels
        current_labels = self._get_all_state_labels(issue_number)

        # Add new state label first so a mid-transition failure does not leave
        # the issue without any state label.
        self._add_label(issue_number, state.to_label())

        # Remove old state labels
        for label in current_labels:
            if label == state.to_label():
                continue
            self._remove_label(issue_number, label)

    def _get_all_state_labels(self, issue_number: int) -> list[str]:
        """Get all state/* labels of an issue."""
        labels = self.issue_port.get_issue_labels(issue_number)
        if labels is None:
            return []
        return [name for name in labels if name.startswith("state/")]

    def has_label(self, issue_number: int, label: str) -> bool:
        """Check whether an issue currently has the given label."""
        labels = self.issue_port.get_issue_labels(issue_number)
        return labels is not None and label in labels

    def confirm_vibe_task(
        self,
        issue_number: int,
        should_exist: bool = True,
    ) -> Literal["confirmed", "advanced", "blocked"]:
        """Confirm vibe-task mirror label with minimum action."""
        labels = self.issue_port.get_issue_labels(issue_number)
        if labels is None:
            return "blocked"

        has_vibe_task = VIBE_TASK_LABEL in labels
        if should_exist and has_vibe_task:
            return "confirmed"
        if (not should_exist) and (not has_vibe_task):
            return "confirmed"

        if should_exist:
            ok = self.issue_port.add_issue_label(issue_number, VIBE_TASK_LABEL)
        else:
            ok = self.issue_port.remove_issue_label(issue_number, VIBE_TASK_LABEL)
        if not ok:
            return "blocked"
        return "advanced"

    def _add_label(self, issue_number: int, label: str) -> None:
        """[Internal] Add label to issue."""
        ok = self.issue_port.add_issue_label(issue_number, label)
        if not ok:
            raise SystemError(f"Failed to add label '{label}' on issue #{issue_number}")

    def _remove_label(self, issue_number: int, label: str) -> None:
        """[Internal] Remove label from issue."""
        ok = self.issue_port.remove_issue_label(issue_number, label)
        if not ok:
            raise SystemError(
                f"Failed to remove label '{label}' on issue #{issue_number}"
            )

    def _ensure_state_label_exists(self, state: IssueState) -> None:
        color, description = STATE_LABEL_META[state]
        ok = self.issue_port.ensure_label_exists(
            state.to_label(),
            color=color,
            description=description,
        )
        if not ok:
            raise SystemError(f"Failed to ensure label '{state.to_label()}' exists")
