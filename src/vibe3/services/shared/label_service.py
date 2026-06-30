"""Thin orchestration layer for issue state labels.

Domain transition rules live in ``vibe3.models.state_machine``.
GitHub label CRUD lives behind ``IssueLabelPort`` in ``vibe3.clients``.
This service only coordinates the two.
"""

from datetime import datetime
from typing import Literal

from loguru import logger

from vibe3.clients import GhIssueLabelPort, IssueLabelPort
from vibe3.config import load_orchestra_config
from vibe3.exceptions import InvalidTransitionError, SystemError
from vibe3.models import (
    STATE_LABEL_META,
    VIBE_TASK_LABEL,
    IssueState,
    StateTransition,
    validate_transition,
)


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

        When multiple state/* labels coexist (stale label not yet cleaned
        up), resolves to the highest-priority one (STATE_PRIORITY_ORDER)
        instead of whichever label the API happened to list first. Picking
        by iteration order let confirm_issue_state() short-circuit on a
        stale label and never clean it up (issue #3182 regression).

        Args:
            issue_number: GitHub issue number

        Returns:
            IssueState: Current state
            None: No state/* label found
        """
        from vibe3.services.shared.labels import get_highest_priority_state

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

        highest = get_highest_priority_state(labels)
        return IssueState.from_label(highest) if highest else None

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
        """Confirm target issue state with minimum action.

        Only short-circuits when the issue carries exactly the target
        state/* label and nothing else. Matching on the highest-priority
        label alone let a stale, lower-priority label coexist forever
        whenever it happened to never conflict with a later target state.
        """
        from vibe3.services.shared.labels import get_state_labels

        labels = self.issue_port.get_issue_labels(issue_number)
        if labels is not None:
            current_states = get_state_labels(labels)
            if current_states == [to_state.to_label()]:
                return "confirmed"
            if to_state.to_label() in current_states:
                # Target is already present (it's the highest-priority
                # label) but a stale lower-priority label coexists. This
                # isn't an FSM transition — go straight to set_state() to
                # clean up the stale label(s) instead of validating a
                # same-state A->A move through transition().
                try:
                    self.set_state(issue_number, to_state)
                except SystemError:
                    return "blocked"
                return "advanced"
        try:
            self.transition(issue_number, to_state, actor=actor, force=force)
        except (InvalidTransitionError, SystemError):
            return "blocked"
        return "advanced"

    def replace_issue_state(
        self,
        issue_number: int,
        target: IssueState,
        *,
        actor: str,
    ) -> Literal["confirmed", "normalized"]:
        """Normalize remote state labels to exactly one target state."""
        from vibe3.services.shared.labels import get_state_labels

        labels = self.issue_port.get_issue_labels(issue_number)
        if labels is None:
            raise SystemError(f"Failed to read state labels on issue #{issue_number}")

        current_states = get_state_labels(labels)
        target_label = target.to_label()
        if current_states == [target_label]:
            return "confirmed"

        self._ensure_state_label_exists(target)
        self._add_label(issue_number, target_label)
        for label in current_states:
            if label != target_label:
                self._remove_label(issue_number, label)

        logger.bind(
            external="github",
            operation="replace_state",
            issue_number=issue_number,
            target_state=target.value,
            actor=actor,
        ).info("Issue state labels normalized")
        return "normalized"

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
        from vibe3.services.shared.labels import get_state_labels

        labels = self.issue_port.get_issue_labels(issue_number)
        if labels is None:
            return []
        return get_state_labels(labels)

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
