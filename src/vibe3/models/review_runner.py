"""Models for review runner service."""

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class ReviewAgentOptions:
    """Immutable configuration for running a review agent.

    This configuration is frozen (immutable) to ensure:
    - Thread safety
    - Predictable behavior
    - Easy testing and debugging

    Attributes:
        agent: The agent preset name (passed to codeagent-wrapper)
        model: Optional model override
        backend: Backend name (for database recording or direct use)
        timeout_seconds: Maximum execution time (default: 600 seconds)

    Usage:
        - Use agent preset: Set agent, leave backend=None
        - Use backend directly: Set backend, leave agent=None
        - Config can have both: agent for codeagent-wrapper, backend for DB recording

    """

    agent: str | None = None
    model: str | None = None
    backend: str | None = None
    timeout_seconds: int = 600


@dataclass(frozen=True)
class ReviewAgentResult:
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

    @classmethod
    def from_completed_process(
        cls, cp: subprocess.CompletedProcess[str]
    ) -> "ReviewAgentResult":
        """Create result from a CompletedProcess."""
        from vibe3.services.review_runner import extract_session_id

        stdout = cp.stdout or ""
        return cls(
            exit_code=cp.returncode,
            stdout=stdout,
            stderr=cp.stderr or "",
            session_id=extract_session_id(stdout),
        )

    def is_success(self) -> bool:
        """Check if the agent run was successful."""
        return self.exit_code == 0
