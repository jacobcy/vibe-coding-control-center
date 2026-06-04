"""Diagnostic message formatting for user-friendly error messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.exceptions.diagnostic_errors import DiagnosticContext


def format_diagnostic_message(resource: str, context: "DiagnosticContext") -> str:
    """Format a user-friendly diagnostic message.

    Args:
        resource: The missing resource identifier
        context: Diagnostic context with search paths and remediation

    Returns:
        Formatted multi-line error message
    """
    lines = [f"Missing {context.resource_type}: {resource}"]
    lines.append("")
    lines.append("Searched paths:")
    for p in context.search_paths:
        lines.append(f"  - {p}")
    if context.profile:
        lines.append(f"Current profile: {context.profile}")
    lines.append(f"Suggested fix: {context.remediation}")
    if context.ref_issue:
        lines.append(f"See issue #{context.ref_issue} for details")
    return "\n".join(lines)


def diagnose_profile() -> str:
    """Get current profile name for diagnostic context.

    Returns:
        Profile name or "unknown" if resolution fails
    """
    try:
        from vibe3.services.convention_resolver import ConventionResolver

        resolver = ConventionResolver.from_repo()
        # Use internal detection method to get profile name
        return resolver._detect_profile()
    except Exception:
        return "unknown"
