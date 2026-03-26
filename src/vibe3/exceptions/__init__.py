"""Unified exception hierarchy for Vibe 3.0."""


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

    pass


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


class SQLiteError(SystemError):
    """SQLite database operation failed."""

    def __init__(self, operation: str, details: str) -> None:
        """Initialize SQLiteError.

        Args:
            operation: Database operation that failed
            details: Error details
        """
        super().__init__(f"SQLite {operation} failed: {details}")
        self.operation = operation


class CommitAnalyzerError(SystemError):
    """CommitAnalyzer git command failed."""

    def __init__(self, operation: str, details: str) -> None:
        """Initialize CommitAnalyzerError.

        Args:
            operation: CommitAnalyzer operation that failed
            details: Error details
        """
        super().__init__(f"CommitAnalyzer {operation} failed: {details}")
        self.operation = operation
        self.details = details


class HookManagerError(SystemError):
    """HookManager hook install/uninstall failed."""

    def __init__(self, operation: str, details: str) -> None:
        """Initialize HookManagerError.

        Args:
            operation: HookManager operation that failed (e.g., 'install', 'uninstall')
            details: Error details
        """
        super().__init__(f"HookManager {operation} failed: {details}")
        self.operation = operation
        self.details = details


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


class FlowNotFoundError(VibeError):
    """Flow does not exist."""

    def __init__(self, flow_slug: str) -> None:
        """Initialize FlowNotFoundError.

        Args:
            flow_slug: Flow slug that was not found
        """
        super().__init__(f"Flow '{flow_slug}' not found", recoverable=False)
        self.flow_slug = flow_slug


class IssueNotFoundError(VibeError):
    """Issue does not exist."""

    def __init__(self, issue_number: int) -> None:
        """Initialize IssueNotFoundError.

        Args:
            issue_number: Issue number that was not found
        """
        super().__init__(f"Issue #{issue_number} not found", recoverable=False)
        self.issue_number = issue_number


class TaskNotFoundError(VibeError):
    """Task does not exist."""

    def __init__(self, task_id: str) -> None:
        """Initialize TaskNotFoundError.

        Args:
            task_id: Task ID that was not found
        """
        super().__init__(f"Task '{task_id}' not found", recoverable=False)
        self.task_id = task_id


# ========== Batch Errors ==========


class BatchError(SystemError):
    """Batch operation partially failed."""

    def __init__(self, message: str, errors: list[dict]) -> None:
        """Initialize BatchError.

        Args:
            message: Summary error message
            errors: List of error details, each with
                at least 'file'/'task' and 'error' keys
        """
        super().__init__(f"{message} ({len(errors)} failures)")
        self.errors = errors


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
