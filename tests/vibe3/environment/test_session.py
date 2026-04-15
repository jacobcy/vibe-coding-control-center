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


class TestClearAllSessions:
    """Tests for SessionRegistryService.clear_all_sessions()."""

    def _make_registry(self, sessions: list[dict]) -> object:
        from unittest.mock import MagicMock

        from vibe3.environment.session_registry import SessionRegistryService

        store = MagicMock()
        store.list_live_runtime_sessions.return_value = sessions
        backend = MagicMock()
        registry = SessionRegistryService(store=store, backend=backend)
        return registry, store

    def test_clear_all_marks_all_sessions_stopped(self) -> None:
        sessions = [
            {"id": 1, "tmux_session": "vibe3-manager-1", "role": "manager"},
            {"id": 2, "tmux_session": None, "role": "planner"},
            {"id": 3, "tmux_session": "vibe3-executor-3", "role": "executor"},
        ]
        registry, store = self._make_registry(sessions)

        cleared = registry.clear_all_sessions()

        assert cleared == 3
        assert store.update_runtime_session.call_count == 3
        for call in store.update_runtime_session.call_args_list:
            assert call.kwargs.get("status") == "stopped" or call.args[1] == "stopped"

    def test_clear_all_no_sessions_returns_zero(self) -> None:
        registry, store = self._make_registry([])
        assert registry.clear_all_sessions() == 0
        store.update_runtime_session.assert_not_called()

    def test_clear_all_does_not_check_tmux(self) -> None:
        """clear_all_sessions skips tmux check — that's the whole point."""
        sessions = [{"id": 1, "tmux_session": "alive-session", "role": "manager"}]
        registry, store = self._make_registry(sessions)

        # Even if tmux is alive, we still clear
        cleared = registry.clear_all_sessions()
        assert cleared == 1
        # _has_tmux_session should NOT be called
        registry._backend.is_session_running.assert_not_called()
