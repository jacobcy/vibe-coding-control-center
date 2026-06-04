"""Missing resource error with diagnostic context."""

from __future__ import annotations

from dataclasses import dataclass

from vibe3.exceptions import UserError
from vibe3.resources.diagnostics import format_diagnostic_message


@dataclass(frozen=True)
class DiagnosticContext:
    """Diagnostic context for missing resource errors.

    Provides structured information about what was searched,
    what profile was active, and how to fix the issue.
    """

    resource_type: str  # e.g. "prompt-recipes", "supervisor-template"
    search_paths: list[str]  # paths that were searched
    profile: str | None  # current profile name
    remediation: str  # suggested fix command or action
    ref_issue: int | None  # related issue number for more info


class MissingResourceError(UserError):
    """Missing configuration or runtime asset with diagnostic context.

    This error provides user-friendly information about what resource
    is missing, where it was searched, and how to fix it.
    """

    def __init__(self, resource: str, context: DiagnosticContext) -> None:
        """Initialize MissingResourceError.

        Args:
            resource: The missing resource identifier
            context: Diagnostic context with search paths and remediation
        """
        self.resource = resource
        self.diagnostic = context
        super().__init__(format_diagnostic_message(resource, context))
