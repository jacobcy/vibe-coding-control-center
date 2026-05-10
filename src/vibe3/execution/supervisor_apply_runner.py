"""Sync execution runner for supervisor apply.

Provides a thin wrapper around run_issue_role_sync for supervisor apply execution.
"""

from vibe3.roles.supervisor import SUPERVISOR_CLI_SYNC_SPEC


def run_supervisor_apply(
    *,
    issue_number: int,
    dry_run: bool = False,
    fresh_session: bool = True,
) -> None:
    """Run supervisor apply for a specific issue.

    This is a thin wrapper that delegates to run_issue_role_sync with
    supervisor-specific configuration. It follows the same pattern as
    run_governance_sync for consistency.

    Args:
        issue_number: GitHub issue number to apply supervisor
        dry_run: If True, print command without executing
        fresh_session: If True, start fresh session (default True for supervisor)
    """
    from vibe3.execution.issue_role_sync_runner import run_issue_role_sync

    run_issue_role_sync(
        issue_number=issue_number,
        dry_run=dry_run,
        fresh_session=fresh_session,
        show_prompt=False,
        spec=SUPERVISOR_CLI_SYNC_SPEC,
    )
