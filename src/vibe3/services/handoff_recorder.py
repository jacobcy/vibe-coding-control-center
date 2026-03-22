"""Handoff recording operations."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient


def record_handoff(
    store: SQLiteClient,
    git_client: GitClient,
    handoff_type: str,
    ref: str,
    next_step: str | None,
    blocked_by: str | None,
    actor: str,
) -> None:
    """Record handoff to store.

    Args:
        store: SQLiteClient instance
        git_client: GitClient instance
        handoff_type: Type of handoff (plan/report/audit)
        ref: Document reference
        next_step: Next step suggestion
        blocked_by: Blocker description
        actor: Actor identifier
    """
    logger.bind(
        domain="handoff",
        action=f"record_{handoff_type}",
        ref=ref,
        actor=actor,
    ).info(f"Recording {handoff_type} handoff")

    branch = git_client.get_current_branch()

    # Determine actor role based on handoff type
    actor_role = "planner_actor" if handoff_type == "plan" else "reviewer_actor"

    # Build update kwargs
    update_kwargs = {
        actor_role: actor,
        "latest_actor": actor,
        "next_step": next_step,
        "blocked_by": blocked_by,
    }

    # Set the appropriate ref field
    if handoff_type == "plan":
        update_kwargs["plan_ref"] = ref
    elif handoff_type == "report":
        update_kwargs["report_ref"] = ref
    else:
        update_kwargs["audit_ref"] = ref

    # Update flow state
    store.update_flow_state(branch, **update_kwargs)

    # Add event
    store.add_event(
        branch,
        f"handoff_{handoff_type}",
        actor,
        f"{handoff_type.capitalize()} recorded: {ref}",
    )

    logger.success(f"{handoff_type.capitalize()} handoff recorded")
