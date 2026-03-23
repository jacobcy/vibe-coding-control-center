"""Review runner service - executes codeagent-wrapper for code review.

This module provides an extensible interface for running different agent types
(Reviewer, Planner, Executor) through codeagent-wrapper.

Design principles:
- Immutable configuration (frozen dataclass)
- Enum-based agent types for type safety and future extension
- Clear separation between configuration and execution

NOTE: This file is in critical_paths to ensure changes trigger thorough review.
"""

import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
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
        agent: The agent preset name (mutually exclusive with backend)
        model: Optional model override (used with backend)
        backend: Backend name (mutually exclusive with agent)
        timeout_seconds: Maximum execution time (default: 600 seconds)

    """

    agent: str | None = None
    model: str | None = None
    backend: str | None = None
    timeout_seconds: int = 600

    def __post_init__(self) -> None:
        """Validate mutually exclusive options."""
        if self.agent and self.backend:
            raise ValueError(
                "agent and backend are mutually exclusive. "
                "Use either agent preset OR backend+model, not both."
            )


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
    def from_completed_process(
        cls, cp: subprocess.CompletedProcess[str]
    ) -> "ReviewAgentResult":
        """Create result from a CompletedProcess."""
        return cls(
            exit_code=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
        )

    def is_success(self) -> bool:
        """Check if the agent run was successful."""
        return self.exit_code == 0


def get_effective_backend(options: ReviewAgentOptions) -> str:
    """Get the effective backend name from options.

    When using agent preset, the preset name serves as the backend identifier.
    When using backend directly, returns the backend name.

    Args:
        options: ReviewAgentOptions with agent or backend set

    Returns:
        Backend name (either preset name or direct backend)
    """
    if options.backend:
        return options.backend
    if options.agent:
        return options.agent
    return "unknown"


def format_agent_actor(options: ReviewAgentOptions) -> str:
    """Format the actor string for handoff records.

    Actor format: '<backend>/<model>' or '<backend>'
    - backend: either agent preset name or direct backend name
    - model: optional model name

    Args:
        options: ReviewAgentOptions with agent/backend/model

    Returns:
        Actor string like 'claude/sonnet' or 'planner' or 'unknown'
    """
    backend = get_effective_backend(options)
    if options.model:
        return f"{backend}/{options.model}"
    return backend


def run_review_agent(
    prompt_file_content: str,
    options: ReviewAgentOptions,
    task: str | None = None,
    dry_run: bool = False,
) -> ReviewAgentResult:
    """Run a review agent using codeagent-wrapper.

    Args:
        prompt_file_content: Content to write to prompt file (review context)
        options: Configuration for the agent run
        task: Optional task/instruction (custom message or default)
        dry_run: If True, print command and prompt without executing

    Returns:
        ReviewAgentResult containing exit code and output

    Raises:
        FileNotFoundError: If codeagent-wrapper is not found
        RuntimeError: If the agent returns a non-zero exit code
        TimeoutExpired: If the agent exceeds the timeout

    """
    import tempfile

    wrapper_path = DEFAULT_WRAPPER_PATH

    # Write prompt file content to temporary file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False
    ) as prompt_file:
        prompt_file.write(prompt_file_content)
        prompt_file_path = prompt_file.name

    try:
        # Build command: wrapper --agent <agent> --prompt-file <file> [task]
        command: list[str] = [str(wrapper_path)]

        # Add agent preset or backend+model
        if options.agent:
            command.extend(["--agent", options.agent])
        elif options.backend:
            command.extend(["--backend", options.backend])
            if options.model:
                command.extend(["--model", options.model])
        else:
            # Fallback to default agent if nothing specified
            command.extend(["--agent", "code-reviewer"])

        # Add prompt file
        command.extend(["--prompt-file", prompt_file_path])

        # Add task if provided
        if task:
            command.append(task)

        # Dry-run mode: print command and prompt
        if dry_run:
            print("=== Command ===")
            print(" ".join(command))
            print(f"\n=== Prompt File: {prompt_file_path} ===")
            print(prompt_file_content)
            if task:
                print(f"\n=== Task ===\n{task}")
            print("\n=== End ===")
            # Return a mock success result
            return ReviewAgentResult(exit_code=0, stdout="[dry-run]", stderr="")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=options.timeout_seconds,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                f"codeagent-wrapper not found at {wrapper_path}. "
                "Please ensure it is installed and accessible."
            ) from None
        except subprocess.TimeoutExpired:
            raise

        # Print output for visibility
        if result.stdout:
            print(result.stdout, end="", flush=True)
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="", flush=True)

        agent_result = ReviewAgentResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

        if not agent_result.is_success():
            stderr_preview = (
                agent_result.stderr[:500]
                if agent_result.stderr
                else (
                    agent_result.stdout[:500] if agent_result.stdout else "(no output)"
                )
            )
            raise RuntimeError(
                f"codeagent-wrapper failed with exit code {agent_result.exit_code}:\n"
                f"{stderr_preview}"
            )

        return agent_result
    finally:
        # Clean up temporary file
        Path(prompt_file_path).unlink(missing_ok=True)
