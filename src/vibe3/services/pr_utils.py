"""PR service utility functions."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models.pr import PRMetadata


def get_metadata_from_flow(store: SQLiteClient, branch: str) -> PRMetadata | None:
    """Read metadata from flow state.

    Args:
        store: SQLiteClient instance
        branch: Branch name

    Returns:
        PR metadata from flow state, or None if flow not found
    """
    flow_data = store.get_flow_state(branch)
    if not flow_data:
        logger.bind(branch=branch).debug("No flow found for branch")
        return None

    metadata = PRMetadata(
        task_issue=flow_data.get("task_issue_number"),
        flow_slug=flow_data.get("flow_slug"),
        spec_ref=flow_data.get("spec_ref"),
        planner=flow_data.get("planner_actor"),
        executor=flow_data.get("executor_actor"),
    )

    logger.bind(
        branch=branch,
        task_issue=metadata.task_issue,
        flow_slug=metadata.flow_slug,
    ).debug("Loaded metadata from flow")

    return metadata


def build_pr_body(body: str, metadata: PRMetadata | None = None) -> str:
    """Build PR body with metadata.

    Args:
        body: Original PR body
        metadata: PR metadata

    Returns:
        Enhanced PR body with metadata section
    """
    if not metadata:
        return body

    metadata_section = "\n\n---\n\n## Vibe3 Metadata\n\n"

    if metadata.task_issue:
        metadata_section += f"**Task Issue:** #{metadata.task_issue}\n"
    if metadata.flow_slug:
        metadata_section += f"**Flow:** {metadata.flow_slug}\n"
    if metadata.spec_ref:
        metadata_section += f"**Spec Ref:** {metadata.spec_ref}\n"
    if metadata.planner:
        metadata_section += f"**Planner:** {metadata.planner}\n"
    if metadata.executor:
        metadata_section += f"**Executor:** {metadata.executor}\n"

    return body + metadata_section
