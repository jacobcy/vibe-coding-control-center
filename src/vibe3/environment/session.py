"""Session management for process persistence."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class TmuxSessionContext:
    """Pure tmux session context (no codeagent dependency)."""

    session_id: str  # Format: vibe3_{prefix}_{timestamp}
    log_path: Optional[Path] = None
    keep_alive_seconds: int = 60


@dataclass
class CodeagentSessionContext:
    """Codeagent session context (optional tmux wrapper)."""

    session_id: str  # Codeagent internal session ID
    tmux_session: Optional[TmuxSessionContext] = None
    sync_mode: bool = False  # Distinguishes sync/async execution


class SessionManager:
    """Unified manager for tmux sessions and codeagent sessions.

    This manager provides two session types:
    1. TmuxSessionContext: Pure tmux sessions for L3 manager execution
    2. CodeagentSessionContext: Codeagent sessions (sync or async with tmux wrapper)

    Key features:
    - Consistent naming convention: vibe3_{prefix}_{timestamp}
    - Automatic log path management
    - Configurable keep-alive for async sessions
    - Session attach and cleanup methods
    """

    def __init__(
        self,
        repo_path: Path,
        log_dir: Optional[Path] = None,
    ):
        """Initialize SessionManager.

        Args:
            repo_path: Path to the main repository
            log_dir: Directory for session logs (defaults to .git/vibe3/logs)
        """
        self.repo_path = repo_path
        self.log_dir = log_dir or (repo_path / ".git" / "vibe3" / "logs")

    # --- Tmux Session Methods ---

    def create_tmux_session(
        self,
        prefix: str,
        keep_alive: int = 60,
    ) -> TmuxSessionContext:
        """Create a pure tmux session (L3 manager execution).

        Args:
            prefix: Session name prefix (e.g., "manager", "plan")
            keep_alive: Seconds to keep session alive after command exits

        Returns:
            TmuxSessionContext with session metadata

        Raises:
            SystemError: If tmux session creation fails
        """
        # Allocate a unique session name
        session_id = self._allocate_session_name(prefix)
        log_path = self._resolve_log_path(session_id)

        # Create tmux session (don't fail on error for compatibility)
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_id],
            cwd=self.repo_path,
            check=False,
            capture_output=True,
            timeout=10,
        )

        logger.info(
            "Created tmux session",
            session=session_id,
            keep_alive=keep_alive,
        )

        return TmuxSessionContext(
            session_id=session_id,
            log_path=log_path,
            keep_alive_seconds=keep_alive,
        )

    def attach_tmux_session(self, context: TmuxSessionContext) -> None:
        """Attach to a tmux session (for human intervention).

        Args:
            context: TmuxSessionContext to attach to
        """
        try:
            subprocess.run(
                ["tmux", "attach", "-t", context.session_id],
                check=False,  # Allow failure (user detaches)
            )
        except KeyboardInterrupt:
            logger.info("Detached from tmux session", session=context.session_id)

    def cleanup_tmux_session(self, context: TmuxSessionContext) -> None:
        """Kill a tmux session immediately.

        Args:
            context: TmuxSessionContext to cleanup
        """
        try:
            subprocess.run(
                ["tmux", "kill-session", "-t", context.session_id],
                check=False,
                capture_output=True,
                timeout=10,
            )
            logger.info("Killed tmux session", session=context.session_id)
        except Exception as exc:
            logger.warning(
                "Failed to kill tmux session",
                session=context.session_id,
                error=str(exc),
            )

    # --- Codeagent Session Methods ---

    def create_codeagent_session(
        self,
        sync_mode: bool = False,
        prefix: Optional[str] = None,
    ) -> CodeagentSessionContext:
        """Create a codeagent session (L2 supervisor execution).

        Args:
            sync_mode: If True, no tmux wrapper (synchronous execution)
            prefix: Optional session name prefix (for async mode)

        Returns:
            CodeagentSessionContext with session metadata

        Raises:
            SystemError: If async tmux session creation fails
        """
        if sync_mode:
            # Synchronous mode: no tmux, direct execution
            return CodeagentSessionContext(
                session_id="sync_stdout",
                sync_mode=True,
            )

        # Async mode: create tmux wrapper
        tmux_ctx = self.create_tmux_session(prefix or "codeagent")
        return CodeagentSessionContext(
            session_id=tmux_ctx.session_id,
            tmux_session=tmux_ctx,
            sync_mode=False,
        )

    # --- Internal Implementation ---

    def _allocate_session_name(self, base_name: str) -> str:
        """Return a non-colliding tmux session name.

        Mimics the behavior of codeagent._allocate_tmux_session_name:
        - Start with base_name
        - If exists, try base_name-2, base_name-3, etc.
        - Return first non-existent name
        """
        candidate = base_name
        counter = 2
        while True:
            probe = subprocess.run(
                ["tmux", "has-session", "-t", candidate],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if probe.returncode != 0:
                return candidate
            candidate = f"{base_name}-{counter}"
            counter += 1

    def _resolve_log_path(self, session_id: str) -> Path:
        """Resolve log file path for a session."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        return self.log_dir / f"{session_id}.log"
