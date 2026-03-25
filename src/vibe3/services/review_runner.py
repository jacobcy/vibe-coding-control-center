"""Review runner service - executes codeagent-wrapper for code review.

This module provides an extensible interface for running different agent types
(Reviewer, Planner, Executor) through codeagent-wrapper.

Design principles:
- Immutable configuration (frozen dataclass)
- Clear separation between configuration and execution

NOTE: This file is in critical_paths to ensure changes trigger thorough review.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Final, cast

from vibe3.clients.git_client import GitClient
from vibe3.models.review_runner import ReviewAgentOptions, ReviewAgentResult

# Default wrapper path
DEFAULT_WRAPPER_PATH: Final[Path] = (
    Path.home() / ".claude" / "bin" / "codeagent-wrapper"
)


def extract_session_id(stdout: str) -> str | None:
    """Extract session ID from codeagent-wrapper output.

    Pattern:
        SESSION_ID: 262f0fea-eacb-4223-b842-b5b5097f94e8
    """
    if not stdout:
        return None
    match = re.search(r"SESSION_ID:\s*([a-f0-9-]{36})", stdout)
    return match.group(1) if match else None


def resolve_actor_backend_model(options: ReviewAgentOptions) -> tuple[str, str | None]:
    """Resolve the actual backend and model for database recording.

    Priority:
    1. If backend is provided (CLI override): use backend/model
    2. If only agent is provided: use agent as backend identifier

    Args:
        options: ReviewAgentOptions with agent/backend/model

    Returns:
        Tuple of (backend, model) for database recording
    """
    if options.backend:
        return options.backend, options.model
    if options.agent:
        return options.agent, options.model
    return "unknown", None


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
    backend, model = resolve_actor_backend_model(options)
    if model:
        return f"{backend}/{model}"
    return backend


def run_review_agent(
    prompt_file_content: str,
    options: ReviewAgentOptions,
    task: str | None = None,
    dry_run: bool = False,
    session_id: str | None = None,
) -> ReviewAgentResult:
    """Run a review agent using codeagent-wrapper.

    Args:
        prompt_file_content: Prompt file content (ignored if session_id provided)
        options: Configuration for the agent run
        task: Optional task/instruction (custom message or default)
        dry_run: If True, print command and prompt without executing
        session_id: Optional session ID to resume an existing session

    Returns:
        ReviewAgentResult containing exit code, output, and session_id

    Raises:
        FileNotFoundError: If codeagent-wrapper is not found
        RuntimeError: If the agent returns a non-zero exit code
        TimeoutExpired: If the agent exceeds the timeout

    """
    import tempfile

    wrapper_path = DEFAULT_WRAPPER_PATH
    prompt_dir = Path.home() / ".codeagent" / "agents"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    # Always write prompt file content, even in resume mode
    # This ensures the correct AST information is available
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, dir=prompt_dir
    ) as prompt_file:
        prompt_file.write(prompt_file_content)
        prompt_file_path = prompt_file.name

    try:
        # Build command: wrapper --agent <agent> --prompt-file <file> [task]
        command: list[str] = [str(wrapper_path)]

        # Add agent preset or backend+model (for both new and resume sessions)
        if options.agent:
            command.extend(["--agent", options.agent])
        elif options.backend:
            command.extend(["--backend", options.backend])
            if options.model:
                command.extend(["--model", options.model])
        else:
            command.extend(["--agent", "code-reviewer"])

        # Add prompt file (always needed for correct AST context)
        command.extend(["--prompt-file", cast(str, prompt_file_path)])

        if session_id:
            # Resume mode with session_id
            command.append("resume")
            command.append(cast(str, session_id))
            if task:
                command.append(task)
            else:
                command.append("continue")
        else:
            # New session mode: wrapper --agent <agent> --prompt-file <file> [task]
            if task:
                command.append(task)

        # Dry-run mode: print command and prompt
        if dry_run:
            print("=== Command ===")
            print(" ".join(command))
            if prompt_file_path:
                print(f"\n=== Prompt File: {prompt_file_path} ===")
                print(prompt_file_content)
            if task:
                print(f"\n=== Task ===\n{task}")
            print("\n=== End ===")
            # Return a mock success result
            return ReviewAgentResult(exit_code=0, stdout="[dry-run]", stderr="")

        try:
            # Get current working directory (worktree or main repo)
            # Use os.getcwd() to respect the current worktree context
            import os
            project_root = os.getcwd()

            # Real-time output using Popen
            stdout_lines = []
            stderr_lines = []

            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_root,  # Execute in current worktree
            )

            # Read output in real-time
            import select

            while process.poll() is None:
                # Check for available output
                reads, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)

                for fd in reads:
                    line = fd.readline()
                    if line:
                        if fd == process.stdout:
                            print(line, end="", flush=True)
                            stdout_lines.append(line)
                        else:
                            print(line, file=sys.stderr, end="", flush=True)
                            stderr_lines.append(line)

            # Read remaining output after process exits
            for line in process.stdout.readlines():
                if line:
                    print(line, end="", flush=True)
                    stdout_lines.append(line)

            for line in process.stderr.readlines():
                if line:
                    print(line, file=sys.stderr, end="", flush=True)
                    stderr_lines.append(line)

            # Create result object
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            class FakeResult:
                def __init__(self, returncode, stdout, stderr):
                    self.returncode = returncode
                    self.stdout = stdout
                    self.stderr = stderr

            result = FakeResult(process.returncode, stdout, stderr)

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
            session_id=extract_session_id(result.stdout),
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
        if prompt_file_path:
            Path(prompt_file_path).unlink(missing_ok=True)
