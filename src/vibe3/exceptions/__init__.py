"""Unified exception hierarchy for Vibe 3.0."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.exceptions.error_classification import (
        classify_error_hybrid,
        get_error_handling_contract,
        is_permanent_code_error,
    )
    from vibe3.exceptions.error_codes import (
        E_AUP_REJECTION,
        E_EXEC_AUTO_SCENE_RESET,
        is_api_error,
        is_model_error,
    )
    from vibe3.exceptions.error_severity import ErrorHandlingContract, ErrorSeverity
    from vibe3.exceptions.git_error_patterns import (
        TRANSIENT_GIT_ERROR_PATTERNS,
        is_transient_git_error,
    )
    from vibe3.exceptions.runtime_errors import GitHubAPIError


class VibeError(Exception):
    """Base exception for all Vibe errors.

    All custom exceptions in Vibe should inherit from this class.
    This enables unified error handling at the CLI layer.
    """

    def __init__(self, message: str, recoverable: bool = False) -> None:
        """Initialize VibeError.

        Args:
            message: Error message to display
            recoverable: Whether user can fix this by adjusting input
        """
        self.message = message
        self.recoverable = recoverable
        super().__init__(message)


# ========== User Errors (Recoverable) ==========


class UserError(VibeError):
    """User input error that can be fixed by adjusting parameters.

    These errors are typically caused by invalid user input and can be
    resolved by the user correcting their command or configuration.
    """

    def __init__(self, message: str) -> None:
        """Initialize UserError.

        Args:
            message: Error message describing what user did wrong
        """
        super().__init__(message, recoverable=True)


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
        from vibe3.exceptions.diagnostics import format_diagnostic_message

        self.resource = resource
        self.diagnostic = context
        super().__init__(format_diagnostic_message(resource, context))


class ConfigError(UserError):
    """Configuration file or setting error."""

    pass


class AgentPresetNotFoundError(UserError):
    """Agent preset not found in repo config/v3/models.json."""

    def __init__(self, preset_name: str) -> None:
        super().__init__(
            f"Agent preset '{preset_name}' not found in config/v3/models.json"
        )
        self.preset_name = preset_name


class SkillNotAvailableError(UserError):
    """Skill not available — no adapter provides it in current profile."""

    def __init__(self, skill: str, profile: str | None = None) -> None:
        profile_hint = (
            f" (current profile: {profile!r})" if profile else " (no profile detected)"
        )
        fix_hint = (
            "Set VIBE_PROFILE=vibe-center or github-flow to enable skill resolution."
        )
        super().__init__(f"Skill '{skill}' not found{profile_hint}. {fix_hint}")
        self.skill = skill


# ========== System Errors (Non-recoverable) ==========


class SystemError(VibeError):
    """System-level error that requires manual intervention."""

    def __init__(self, message: str) -> None:
        super().__init__(message, recoverable=False)


class AgentExecutionError(SystemError):
    """Agent execution failed (wrapper/API/backend error)."""

    def __init__(
        self,
        message: str,
        log_path: Path | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.log_path: Path | None = log_path
        self.metadata: dict[str, str] | None = metadata


class ModelsJsonSyncError(SystemError):
    """Failed to sync ~/.codeagent/models.json for wrapper execution."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Failed to sync ~/.codeagent/models.json: {reason}")
        self.reason = reason


class GitError(SystemError):
    """Git operation failed."""

    def __init__(self, operation: str, details: str) -> None:
        super().__init__(f"Git {operation} failed: {details}")
        self.operation = operation
        self.details = details


class GitHubError(SystemError):
    """GitHub API error."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"GitHub API error ({status_code}): {message}")
        self.status_code = status_code


class SerenaError(SystemError):
    """Serena code analysis error."""

    def __init__(self, operation: str, details: str) -> None:
        super().__init__(f"Serena {operation} failed: {details}")
        self.operation = operation


# ========== Business Errors ==========


class PRNotFoundError(VibeError):
    """PR does not exist."""

    def __init__(self, pr_number: int) -> None:
        super().__init__(f"PR #{pr_number} not found", recoverable=False)
        self.pr_number = pr_number


# ========== Orchestration Errors ==========


class CapacityDeferredError(VibeError):
    """Dispatch deferred due to capacity limits.

    This is not a failure — it signals that the dispatch should be
    retried later when capacity becomes available.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, recoverable=True)


class InvalidTransitionError(UserError):
    """Invalid state transition in orchestration state machine."""

    def __init__(self, from_state: str | None, to_state: str) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition: {from_state or 'None'} -> {to_state}")


class InvalidBranchLinkError(SystemError):
    """Base branch illegally linked to issue in flow_issue_links."""

    def __init__(self, branch: str, issue_number: int) -> None:
        self.branch = branch
        self.issue_number = issue_number
        super().__init__(
            f"Invalid branch '{branch}' linked to issue #{issue_number}. "
            f"Base branches cannot have flow records. "
            f'Fix: sqlite3 <db> "DELETE FROM flow_issue_links '
            f"WHERE branch='{branch}' AND issue_number={issue_number}\""
        )


# Error classification and tracking references:
#   from vibe3.exceptions.error_classification import classify_error
#   from vibe3.exceptions.error_codes import E_MODEL_NOT_FOUND, ...
#   from vibe3.services.shared.errors import record_error


# Lazy imports to avoid circular dependencies
_LAZY_IMPORTS = {
    "E_AUP_REJECTION": "vibe3.exceptions.error_codes",
    "E_EXEC_AUTO_SCENE_RESET": "vibe3.exceptions.error_codes",
    "E_ISSUE_FAILED": "vibe3.exceptions.error_codes",
    "ErrorHandlingContract": "vibe3.exceptions.error_severity",
    "ErrorSeverity": "vibe3.exceptions.error_severity",
    "GitHubAPIError": "vibe3.exceptions.runtime_errors",
    "TRANSIENT_GIT_ERROR_PATTERNS": "vibe3.exceptions.git_error_patterns",
    "classify_error_hybrid": "vibe3.exceptions.error_classification",
    "is_permanent_code_error": "vibe3.exceptions.error_classification",
    "get_error_handling_contract": "vibe3.exceptions.error_classification",
    "is_api_error": "vibe3.exceptions.error_codes",
    "is_model_error": "vibe3.exceptions.error_codes",
    "is_transient_git_error": "vibe3.exceptions.git_error_patterns",
}


def __getattr__(name: str) -> object:
    """Lazy import symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        module_path = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(module_path)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgentExecutionError",
    "AgentPresetNotFoundError",
    "CapacityDeferredError",
    "ConfigError",
    "DiagnosticContext",
    "E_AUP_REJECTION",
    "E_EXEC_AUTO_SCENE_RESET",
    "E_ISSUE_FAILED",
    "ErrorHandlingContract",
    "ErrorSeverity",
    "GitError",
    "GitHubAPIError",
    "GitHubError",
    "InvalidBranchLinkError",
    "InvalidTransitionError",
    "MissingResourceError",
    "ModelsJsonSyncError",
    "PRNotFoundError",
    "TRANSIENT_GIT_ERROR_PATTERNS",
    "SerenaError",
    "SkillNotAvailableError",
    "SystemError",
    "UserError",
    "VibeError",
    "classify_error_hybrid",
    "is_permanent_code_error",
    "get_error_handling_contract",
    "is_api_error",
    "is_model_error",
    "is_transient_git_error",
]
