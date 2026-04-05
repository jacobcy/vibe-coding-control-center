"""Helpers for resolving issue numbers to canonical flow branches."""

from collections.abc import Iterable

ISSUE_BRANCH_PATTERNS: tuple[str, ...] = (
    "task/issue-{issue_number}",
    "dev/issue-{issue_number}",
)


def iter_issue_branch_candidates(issue_number: int) -> Iterable[str]:
    """Yield supported branch candidates for an issue number."""
    for pattern in ISSUE_BRANCH_PATTERNS:
        yield pattern.format(issue_number=issue_number)


def resolve_issue_branch_input(branch: str | None, flow_service: object) -> str | None:
    """Resolve numeric issue input to an existing task/dev branch.

    If ``branch`` is a plain number like ``436``, this helper checks supported
    branch patterns in order and returns the first one that already exists in the
    local flow store.
    """
    if branch is None:
        return None

    stripped = branch.strip()
    if not stripped.isdigit():
        return stripped

    issue_number = int(stripped)
    get_flow_state = getattr(flow_service, "get_flow_state")

    for candidate in iter_issue_branch_candidates(issue_number):
        if get_flow_state(candidate):
            return candidate

    checked = ", ".join(iter_issue_branch_candidates(issue_number))
    raise RuntimeError(
        f"unable to resolve issue #{issue_number} to an existing branch ({checked})"
    )
