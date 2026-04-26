"""Unified exception hierarchy for Vibe 3.0."""

from __future__ import annotations

from pathlib import Path


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


class ConfigError(UserError):
    """Configuration file or setting error."""

    pass


class AgentPresetNotFoundError(UserError):
    """Agent preset not found in repo config/models.json.

    Raised when an agent preset name is specified but cannot be resolved
    to backend/model from config/models.json.

    This indicates a configuration error that must be fixed before execution.
    """

    def __init__(self, preset_name: str) -> None:
        """Initialize AgentPresetNotFoundError.

        Args:
            preset_name: The agent preset name that was not found
        """
        super().__init__(
            f"Agent preset '{preset_name}' not found in config/models.json"
        )
        self.preset_name = preset_name


# ========== System Errors (Non-recoverable) ==========


class SystemError(VibeError):
    """System-level error that requires manual intervention.

    These errors indicate problems with the system environment,
    external dependencies, or unexpected failures.
    """

    def __init__(self, message: str) -> None:
        """Initialize SystemError.

        Args:
            message: Error message describing the system failure
        """
        super().__init__(message, recoverable=False)


class AgentExecutionError(SystemError):
    """Agent execution failed (wrapper/API/backend error)."""

    def __init__(self, message: str, log_path: Path | None = None) -> None:
        super().__init__(message)
        self.log_path: Path | None = log_path


class ModelsJsonSyncError(SystemError):
    """Failed to sync ~/.codeagent/models.json for wrapper execution.

    Raised when the resolved backend/model cannot be synced to the
    wrapper's config file, preventing proper execution.

    This indicates a sync or permissions issue.
    """

    def __init__(self, reason: str) -> None:
        """Initialize ModelsJsonSyncError.

        Args:
            reason: The reason why sync failed
        """
        super().__init__(f"Failed to sync ~/.codeagent/models.json: {reason}")
        self.reason = reason


class GitError(SystemError):
    """Git operation failed."""

    def __init__(self, operation: str, details: str) -> None:
        """Initialize GitError.

        Args:
            operation: Git operation that failed (e.g., 'commit', 'push')
            details: Error details from git command
        """
        super().__init__(f"Git {operation} failed: {details}")
        self.operation = operation
        self.details = details


class GitHubError(SystemError):
    """GitHub API error."""

    def __init__(self, status_code: int, message: str) -> None:
        """Initialize GitHubError.

        Args:
            status_code: HTTP status code from GitHub API
            message: Error message from GitHub API
        """
        super().__init__(f"GitHub API error ({status_code}): {message}")
        self.status_code = status_code


class SerenaError(SystemError):
    """Serena code analysis error."""

    def __init__(self, operation: str, details: str) -> None:
        """Initialize SerenaError.

        Args:
            operation: Serena operation that failed
            details: Error details
        """
        super().__init__(f"Serena {operation} failed: {details}")
        self.operation = operation


# ========== Business Errors ==========


class PRNotFoundError(VibeError):
    """PR does not exist."""

    def __init__(self, pr_number: int) -> None:
        """Initialize PRNotFoundError.

        Args:
            pr_number: PR number that was not found
        """
        super().__init__(f"PR #{pr_number} not found", recoverable=False)
        self.pr_number = pr_number


# ========== Orchestration Errors ==========


class InvalidTransitionError(UserError):
    """Invalid state transition in orchestration state machine."""

    def __init__(self, from_state: str | None, to_state: str) -> None:
        """Initialize InvalidTransitionError.

        Args:
            from_state: Source state (or None if no prior state)
            to_state: Target state
        """
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition: {from_state or 'None'} -> {to_state}")
