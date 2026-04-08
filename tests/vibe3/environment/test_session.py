"""Tests for SessionManager safety improvements."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.environment.session import SessionManager, TmuxSessionContext


class TestSessionManagerSafety:
    """Tests for SessionManager error handling and safety checks."""

    def test_create_tmux_session_raises_on_failure(self, tmp_path: Path) -> None:
        """SessionManager should raise SystemError when tmux creation fails."""
        from vibe3.exceptions import SystemError as VibeSystemError

        manager = SessionManager(repo_path=tmp_path)

        # Mock _allocate_session_name first (called inside create_tmux_session)
        with patch.object(
            manager, "_allocate_session_name", return_value="test-session"
        ):
            # Mock subprocess.run in the session module
            with patch("vibe3.environment.session.subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=["tmux", "new-session"],
                    returncode=1,
                    stdout="",
                    stderr="session already exists",
                )

                with pytest.raises(VibeSystemError) as exc_info:
                    manager.create_tmux_session("test-session")

                assert "session already exists" in str(exc_info.value)

    def test_create_tmux_session_raises_on_permission_denied(
        self, tmp_path: Path
    ) -> None:
        """SessionManager should raise SystemError on permission errors."""
        from vibe3.exceptions import SystemError as VibeSystemError

        manager = SessionManager(repo_path=tmp_path)

        # Mock _allocate_session_name first
        with patch.object(
            manager, "_allocate_session_name", return_value="test-session"
        ):
            # Mock subprocess.run in the session module
            with patch("vibe3.environment.session.subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=["tmux", "new-session"],
                    returncode=1,
                    stdout="",
                    stderr="permission denied",
                )

                with pytest.raises(VibeSystemError) as exc_info:
                    manager.create_tmux_session("test-session")

                assert "permission denied" in str(exc_info.value)

    def test_create_tmux_session_succeeds_when_tmux_works(self, tmp_path: Path) -> None:
        """SessionManager should create session successfully when tmux works."""
        manager = SessionManager(repo_path=tmp_path)

        with patch("subprocess.run") as mock_run:
            # Mock _allocate_session_name to return a fixed name
            with patch.object(
                manager, "_allocate_session_name", return_value="test-session-123"
            ):
                mock_run.return_value = subprocess.CompletedProcess(
                    args=["tmux", "new-session"],
                    returncode=0,
                    stdout="",
                    stderr="",
                )

                context = manager.create_tmux_session("test")

        assert isinstance(context, TmuxSessionContext)
        assert context.session_id == "test-session-123"
