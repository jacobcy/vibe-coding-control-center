"""Handoff template generation."""


def get_handoff_template(branch: str) -> str:
    """Get minimal handoff template.

    Args:
        branch: Current branch name

    Returns:
        Template string for new handoff files
    """
    return f"""# Handoff: {branch}

> This is a lightweight handoff file for agent-to-agent communication.
> It is NOT a source of truth - all authoritative data is in the SQLite store.

## Meta

- Branch: {branch}
- Updated at: TBD
- Latest actor: unknown

## Summary

<!-- Brief summary of current state -->

## Findings

<!-- Open findings and observations -->

## Blockers

<!-- Current blockers -->

## Next Actions

<!-- Suggested next actions -->

## Key Files

<!-- Important files for the next agent -->

## Evidence Refs

<!-- Links to plans, reports, PRs, issues, or logs -->

## Updates

<!-- Append-only lightweight updates -->
"""
