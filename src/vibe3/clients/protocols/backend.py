"""BackendProtocol — Protocol for backend operations (tmux, execution).

Import paths:
    # Recommended (explicit source)
    from vibe3.clients.protocols.backend import BackendProtocol

"""

from pathlib import Path
from typing import Protocol

from vibe3.models import AgentOptions, AgentResult, AsyncExecutionHandle


class BackendProtocol(Protocol):
    """Protocol for backend operations (tmux, execution).

    Used for dependency injection to avoid architecture layer violations.
    Services layer depends on this protocol, concrete implementation
    (CodeagentBackend) is injected at handler/orchestration layer.
    """

    def has_tmux_session(self, session_name: str) -> bool:
        """Check if tmux session exists.

        Args:
            session_name: Exact tmux session name to check

        Returns:
            True if session exists, False otherwise
        """
        ...

    def run(
        self,
        prompt: str,
        options: AgentOptions,
        task: str | None = None,
        dry_run: bool = False,
        session_id: str | None = None,
        cwd: Path | None = None,
    ) -> AgentResult:
        """Run agent synchronously.

        Args:
            prompt: Prompt content
            options: Agent execution options
            task: Optional task description
            dry_run: If True, print command without executing
            session_id: Optional session ID to resume
            cwd: Working directory

        Returns:
            Agent execution result
        """
        ...

    def start_async(
        self,
        prompt: str,
        options: AgentOptions,
        *,
        task: str | None = None,
        session_id: str | None = None,
        execution_name: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        keep_alive_seconds: int = 0,
    ) -> AsyncExecutionHandle:
        """Start agent asynchronously in tmux.

        Args:
            prompt: Prompt content
            options: Agent execution options
            task: Optional task description
            session_id: Optional session ID to resume
            execution_name: Unique execution name for session and logs
            cwd: Working directory
            env: Optional environment variable overrides
            keep_alive_seconds: Seconds to keep tmux session alive after completion

        Returns:
            Async execution handle with session and log info
        """
        ...


__all__ = ["BackendProtocol"]
