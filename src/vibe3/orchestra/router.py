"""State-to-command router."""

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.config import STATE_TRIGGERS
from vibe3.orchestra.models import IssueInfo, Trigger


class Router:
    """Routes state changes to command triggers."""

    def route(
        self, issue: IssueInfo, previous_state: IssueState | None
    ) -> Trigger | None:
        """Determine if a state change should trigger a command.

        Args:
            issue: Issue information
            previous_state: Previous state (from cache)

        Returns:
            Trigger if a command should be executed, None otherwise
        """
        current_state = issue.state

        if current_state is None:
            return None

        if current_state == previous_state:
            return None

        for trigger_config in STATE_TRIGGERS:
            if (
                trigger_config.from_state == previous_state
                and trigger_config.to_state == current_state
            ):
                return Trigger(
                    issue=issue,
                    from_state=previous_state,
                    to_state=current_state,
                    command=trigger_config.command,
                    args=trigger_config.args,
                )

        return None
