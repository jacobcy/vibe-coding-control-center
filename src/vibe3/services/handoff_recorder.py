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
    session_id: str | None = None,
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
        session_id: Optional session ID from codeagent-wrapper
    """
    logger.bind(
        domain="handoff",
        action=f"record_{handoff_type}",
        ref=ref,
        actor=actor,
        session_id=session_id,
    ).info(f"Recording {handoff_type} handoff")

    branch = git_client.get_current_branch()

    # Determine actor role and session role based on handoff type
    if handoff_type == "plan":
        actor_role = "planner_actor"
        session_role = "planner_session_id"
    elif handoff_type == "report":
        actor_role = "executor_actor"
        session_role = "executor_session_id"
    else:  # audit
        actor_role = "reviewer_actor"
        session_role = "reviewer_session_id"

    # Build update kwargs
    update_kwargs = {
        actor_role: actor,
        "latest_actor": actor,
        "next_step": next_step,
        "blocked_by": blocked_by,
    }

    if session_id:
        update_kwargs[session_role] = session_id

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
