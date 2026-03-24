"""Label integration helpers for vibe3 commands."""

from loguru import logger

from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService


def transition_issue_state(
    issue_number: int | None,
    to_state: IssueState,
    actor: str,
) -> bool:
    """Transition issue state with graceful degradation.

    Args:
        issue_number: GitHub issue number (None = no issue bound)
        to_state: Target state
        actor: Actor identifier (e.g., "agent:plan")

    Returns:
        True if transition succeeded, False otherwise
    """
    if issue_number is None:
        logger.bind(domain="label").debug("No issue bound, skipping state transition")
        return False

    try:
        service = LabelService()
        service.transition(issue_number, to_state, actor)
        logger.bind(
            domain="label",
            issue_number=issue_number,
            to_state=to_state.value,
            actor=actor,
        ).info("Issue state transitioned")
        return True
    except Exception as e:
        logger.bind(
            domain="label",
            issue_number=issue_number,
            to_state=to_state.value,
            error=str(e),
        ).warning("Failed to transition issue state")
        return False


def transition_to_claimed(issue_number: int | None) -> bool:
    """Transition issue to claimed state (for plan command)."""
    return transition_issue_state(issue_number, IssueState.CLAIMED, "agent:plan")


def transition_to_in_progress(issue_number: int | None) -> bool:
    """Transition issue to in-progress state (for run command)."""
    return transition_issue_state(issue_number, IssueState.IN_PROGRESS, "agent:run")


def transition_to_review(issue_number: int | None) -> bool:
    """Transition issue to review state (for review command)."""
    return transition_issue_state(issue_number, IssueState.REVIEW, "agent:review")
