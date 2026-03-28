"""PR service utility functions."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_issues_ops import parse_linked_issues
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
        branch=branch,
        task_issue=flow_data.get("task_issue_number"),
        flow_slug=flow_data.get("flow_slug"),
        spec_ref=flow_data.get("spec_ref"),
        planner=flow_data.get("planner_actor"),
        executor=flow_data.get("executor_actor"),
        reviewer=flow_data.get("reviewer_actor"),
        latest=flow_data.get("latest_actor"),
    )

    logger.bind(
        branch=branch,
        task_issue=metadata.task_issue,
        flow_slug=metadata.flow_slug,
    ).debug("Loaded metadata from flow")

    return metadata


def _has_issue_linked(body: str, issue_number: int) -> bool:
    """Check if body already contains a GitHub auto-close keyword for the issue.

    Args:
        body: PR body text
        issue_number: Issue number to check

    Returns:
        True if a linking keyword (Closes/Fixes/Resolves #<n>) already exists
    """
    return issue_number in parse_linked_issues(body)


def _build_linked_section(metadata: PRMetadata, body: str) -> str:
    """Build the GitHub auto-link section for the bound task issue.

    Injects ``Closes #<n>`` at the top of the body unless the body already
    references the same issue with a linking keyword.

    Args:
        metadata: PR metadata (may contain task_issue)
        body: Original PR body

    Returns:
        Linking line with trailing blank line, or empty string
    """
    if not metadata.task_issue:
        return ""
    if _has_issue_linked(body, metadata.task_issue):
        return ""
    return f"Closes #{metadata.task_issue}\n\n"


def build_pr_body(body: str, metadata: PRMetadata | None = None) -> str:
    """Build PR body with issue linkage and contributor signature.

    - If a task issue is bound, prepends ``Closes #<n>`` to trigger GitHub's
      native issue-PR linkage (unless already present).
    - If flow_state contains non-placeholder actors, appends a Contributors
      section with normalized, deduplicated signatures.
    """
    if not metadata:
        return body

    linked_section = _build_linked_section(metadata, body)

    contributors = metadata.contributors
    if not contributors:
        return linked_section + body

    signature = "\n\n---\n\n" + "## Contributors\n\n" + ", ".join(contributors) + "\n"
    return linked_section + body + signature
