"""Review runner service - executes codeagent-wrapper for code review.

This module provides an extensible interface for running different agent types
(Reviewer, Planner, Executor) through codeagent-wrapper.

Design principles:
- Immutable configuration (frozen dataclass)
- Enum-based agent types for type safety and future extension
- Clear separation between configuration and execution

NOTE: This file is in critical_paths to ensure changes trigger thorough review.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from subprocess import CompletedProcess, run
from typing import Final


class AgentType(str, Enum):
    """Supported agent types for codeagent-wrapper.

    Extensible for future agent types (planner, executor, etc.)
    """

    CODEX = "codex"
    PLANNER = "planner"
    EXECUTOR = "executor"


class AgentBackend(str, Enum):
    """Supported backends for codeagent-wrapper.

    Extensible for future backends (claude, etc.)
    """

    CODEX = "codex"
    CLAUDE = "claude"


# Default wrapper path
DEFAULT_WRAPPER_PATH: Final[Path] = (
    Path.home() / ".claude" / "bin" / "codeagent-wrapper"
)


@dataclass(frozen=True)
class ReviewAgentOptions:
    """Immutable configuration for running a review agent.

    This configuration is frozen (immutable) to ensure:
    - Thread safety
    - Predictable behavior
    - Easy testing and debugging

    Attributes:
        agent: The agent type to use (default: CODEX for reviewer)
        backend: The backend to use (default: CODEX)
        model: Optional model override (e.g., "gpt-5.4", "claude-3-opus")
        timeout_seconds: Maximum execution time (default: 600 seconds)

    """

    agent: AgentType = AgentType.CODEX
    backend: AgentBackend = AgentBackend.CODEX
    model: str | None = None
    timeout_seconds: int = 600


@dataclass(frozen=True)
class ReviewAgentResult:
    """Result from running a review agent.

    Attributes:
        exit_code: The exit code from codeagent-wrapper (0 = success)
        stdout: Standard output from the agent
        stderr: Standard error from the agent

    """

    exit_code: int
    stdout: str
    stderr: str

    @classmethod
    def from_completed_process(cls, cp: CompletedProcess[str]) -> "ReviewAgentResult":
        """Create result from a CompletedProcess."""
        return cls(
            exit_code=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
        )

    def is_success(self) -> bool:
        """Check if the agent run was successful."""
        return self.exit_code == 0


def run_review_agent(prompt: str, options: ReviewAgentOptions) -> ReviewAgentResult:
    """Run a review agent using codeagent-wrapper.

    Args:
        prompt: The prompt/instructions to send to the agent
        options: Configuration for the agent run

    Returns:
        ReviewAgentResult containing exit code and output

    Raises:
        FileNotFoundError: If codeagent-wrapper is not found
        RuntimeError: If the agent returns a non-zero exit code
        TimeoutExpired: If the agent exceeds the timeout

    """
    wrapper_path = DEFAULT_WRAPPER_PATH

    # Build command
    command: list[str] = [
        str(wrapper_path),
        "--backend",
        options.backend.value,
    ]

    if options.model:
        command.extend(["--model", options.model])

    # Add stdin input and working directory
    command.extend(["-", "."])

    try:
        result = run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=options.timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            f"codeagent-wrapper not found at {wrapper_path}. "
            "Please ensure it is installed and accessible."
        ) from None

    agent_result = ReviewAgentResult.from_completed_process(result)

    if not agent_result.is_success():
        stderr_preview = (
            agent_result.stderr[:500] if agent_result.stderr else "(no stderr)"
        )
        raise RuntimeError(
            f"codeagent-wrapper failed with exit code {agent_result.exit_code}:\n"
            f"{stderr_preview}"
        )

    return agent_result
