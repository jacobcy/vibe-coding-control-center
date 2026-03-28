"""PR service utility functions."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.exceptions import GitError, UserError
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
    """Build PR body with metadata.

    If a task issue is bound, prepends ``Closes #<n>`` to trigger GitHub's
    native issue-PR linkage (unless the body already contains a linking
    keyword for that issue).

    Args:
        body: Original PR body
        metadata: PR metadata

    Returns:
        Enhanced PR body with linking section and metadata
    """
    if not metadata:
        return body

    linked_section = _build_linked_section(metadata, body)
    metadata_section = "\n\n---\n\n## Vibe3 Metadata\n\n"

    if metadata.branch:
        metadata_section += f"**Branch:** {metadata.branch}\n"
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
    if metadata.reviewer:
        metadata_section += f"**Reviewer:** {metadata.reviewer}\n"

    contributors = metadata.contributors
    if contributors:
        metadata_section += "\n**Contributors:** " + ", ".join(contributors) + "\n"

    return linked_section + body + metadata_section


def check_upstream_conflicts(
    git_client: GitClient,
    action: str,
    base_branch: str = "main",
    remote: str = "origin",
) -> None:
    """Fetch base branch and dry-run merge to detect conflicts.

    On conflict: raise UserError to halt the calling command.
    On network/fetch failure: log warning and continue (non-blocking).

    Args:
        git_client: GitClient instance for fetch and merge operations
        action: Context label for log/error messages (e.g. "create", "ready")
        base_branch: Target base branch for the PR (branch name or remote ref)
        remote: Remote name to fetch from

    Raises:
        UserError: When merge conflicts are detected
    """
    prefixed = base_branch.startswith(f"{remote}/")
    target = base_branch if prefixed else f"{remote}/{base_branch}"
    fetch_ref = base_branch.removeprefix(f"{remote}/") if prefixed else base_branch
    try:
        git_client.fetch(remote, fetch_ref)
    except GitError:
        logger.bind(domain="pr", action=action).warning(
            f"Failed to fetch {target}, skipping conflict check"
        )
        return

    if git_client.check_merge_conflicts(target):
        raise UserError(
            f"Merge conflict detected between current branch and {target}\n"
            f"Resolve before {action}:\n"
            f"  1. git rebase {target}\n"
            f"  2. Resolve any conflicts\n"
            f"  3. Re-run vibe3 pr {action}"
        )
