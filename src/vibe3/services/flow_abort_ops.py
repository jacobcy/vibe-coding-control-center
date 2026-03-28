"""Flow abort operation helpers."""

from typing import Any

from loguru import logger

from vibe3.clients.git_client import GitClient


def abort_flow_impl(store: Any, branch: str, actor: str = "workflow") -> None:
    """Abort flow and delete branch."""
    git = GitClient()

    logger.bind(domain="flow", action="abort", branch=branch).info("Aborting flow")

    flow_data = store.get_flow_state(branch)
    if not flow_data:
        raise RuntimeError(f"Flow not found for branch {branch}")

    if git.branch_exists(branch):
        git.delete_branch(branch, force=True)

    try:
        git.delete_remote_branch(branch)
    except Exception:
        logger.bind(domain="flow", action="abort", branch=branch).warning(
            "Failed to delete remote branch, continuing"
        )

    store.update_flow_state(branch, flow_status="aborted", latest_actor=actor)
    store.add_event(
        branch,
        "flow_aborted",
        actor,
        f"Flow aborted, branch '{branch}' deleted",
    )
