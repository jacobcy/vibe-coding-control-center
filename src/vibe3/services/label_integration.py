"""Label integration helpers for vibe3 commands."""

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService


class LabelTransitionResult:
    """Result of a label transition attempt."""

    def __init__(
        self,
        success: bool,
        issue_number: int | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.issue_number = issue_number
        self.error = error


def transition_issue_state(
    issue_number: int | None,
    to_state: IssueState,
    actor: str,
) -> LabelTransitionResult:
    """Transition issue state.

    Args:
        issue_number: GitHub issue number (None = no issue bound)
        to_state: Target state
        actor: Actor identifier (e.g., "agent:plan")

    Returns:
        LabelTransitionResult with success status and error details
    """
    if issue_number is None:
        logger.bind(domain="label").debug("No issue bound, skipping state transition")
        return LabelTransitionResult(success=False, error="no_issue_bound")

    try:
        service = LabelService()
        result = service.confirm_issue_state(issue_number, to_state, actor)
        if result == "blocked":
            return LabelTransitionResult(
                success=False,
                issue_number=issue_number,
                error="state_transition_blocked",
            )
        logger.bind(
            domain="label",
            issue_number=issue_number,
            to_state=to_state.value,
            actor=actor,
        ).info("Issue state transitioned")
        return LabelTransitionResult(success=True, issue_number=issue_number)
    except Exception as e:
        logger.bind(
            domain="label",
            issue_number=issue_number,
            to_state=to_state.value,
            error=str(e),
        ).error(f"Failed to transition issue state: {e}")
        return LabelTransitionResult(
            success=False, issue_number=issue_number, error=str(e)
        )


def transition_to_claimed(issue_number: int | None) -> LabelTransitionResult:
    """Transition issue to claimed state (for plan command)."""
    return transition_issue_state(issue_number, IssueState.CLAIMED, "agent:plan")


def transition_to_in_progress(issue_number: int | None) -> LabelTransitionResult:
    """Transition issue to in-progress state (for run command)."""
    return transition_issue_state(issue_number, IssueState.IN_PROGRESS, "agent:run")


def transition_to_review(issue_number: int | None) -> LabelTransitionResult:
    """Transition issue to review state (for review command)."""
    return transition_issue_state(issue_number, IssueState.REVIEW, "agent:review")
