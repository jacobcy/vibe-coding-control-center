"""Models for agent execution (used by plan/run/review commands)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentOptions:
    """Immutable configuration for running an agent.

    This configuration is frozen (immutable) to ensure:
    - Thread safety
    - Predictable behavior
    - Easy testing and debugging

    Attributes:
        agent: The agent preset name (passed to codeagent-wrapper)
        model: Optional model override
        backend: Backend name (for database recording or direct use)
        worktree: Whether to pass --worktree to codeagent-wrapper
        timeout_seconds: Maximum execution time (default: 600 seconds)

    Usage:
        - Use agent preset: Set agent, leave backend=None
        - Use backend directly: Set backend, leave agent=None
        - Config can have both: agent for codeagent-wrapper, backend for DB recording

    """

    agent: str | None = None
    model: str | None = None
    backend: str | None = None
    worktree: bool = False
    timeout_seconds: int = 600


@dataclass(frozen=True)
class AgentResult:
    """Result from running a review agent.

    Attributes:
        exit_code: The exit code from codeagent-wrapper (0 = success)
        stdout: Standard output from the agent
        stderr: Standard error from the agent
        session_id: Optional session ID from codeagent-wrapper

    """

    exit_code: int
    stdout: str
    stderr: str
    session_id: str | None = None

    def is_success(self) -> bool:
        """Check if the agent run was successful."""
        return self.exit_code == 0
