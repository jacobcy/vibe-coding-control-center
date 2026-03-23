"""Label service for GitHub state/* label operations."""

import subprocess
from datetime import datetime

from loguru import logger

from vibe3.exceptions import InvalidTransitionError
from vibe3.models.orchestration import (
    ALLOWED_TRANSITIONS,
    FORBIDDEN_TRANSITIONS,
    IssueState,
    StateTransition,
)


class LabelService:
    """GitHub state/* label operations service.

    This is the core state machine, providing Python API for other services.
    No CLI commands exposed.
    """

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

        result = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(issue_number),
                "--json",
                "labels",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            logger.bind(external="github", error=result.stderr).warning(
                f"Failed to get issue #{issue_number}"
            )
            return None

        import json

        data = json.loads(result.stdout)
        labels = data.get("labels", [])

        for label in labels:
            name = label.get("name", "")
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
        if not force and from_state is not None:
            if (from_state, to_state) in FORBIDDEN_TRANSITIONS:
                raise InvalidTransitionError(from_state.value, to_state.value)
            if (from_state, to_state) not in ALLOWED_TRANSITIONS:
                raise InvalidTransitionError(from_state.value, to_state.value)

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

    def set_state(self, issue_number: int, state: IssueState) -> None:
        """Directly set state (internal method, atomically replace state/* labels).

        Args:
            issue_number: GitHub issue number
            state: Target state
        """
        # Get current state labels
        current_labels = self._get_all_state_labels(issue_number)

        # Remove old state labels
        for label in current_labels:
            self._remove_label(issue_number, label)

        # Add new state label
        self._add_label(issue_number, state.to_label())

    def _get_all_state_labels(self, issue_number: int) -> list[str]:
        """Get all state/* labels of an issue."""
        result = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(issue_number),
                "--json",
                "labels",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return []

        import json

        data = json.loads(result.stdout)
        labels = data.get("labels", [])

        return [
            label.get("name", "")
            for label in labels
            if label.get("name", "").startswith("state/")
        ]

    def _add_label(self, issue_number: int, label: str) -> None:
        """[Internal] Add label to issue."""
        subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--add-label", label],
            capture_output=True,
            text=True,
            check=True,
        )

    def _remove_label(self, issue_number: int, label: str) -> None:
        """[Internal] Remove label from issue."""
        subprocess.run(
            ["gh", "issue", "edit", str(issue_number), "--remove-label", label],
            capture_output=True,
            text=True,
            check=True,
        )
