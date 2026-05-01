"""Unit tests for WorktreeOwnershipGuard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.worktree_ownership_guard import (
    WorktreeOwnerMismatchError,
    ensure_worktree_ownership,
    get_current_session_id,
    get_worktree_owner,
    takeover_worktree,
)


class TestGetCurrentSessionId:
    """Tests for get_current_session_id."""

    def test_returns_none_outside_tmux(self) -> None:
        """Outside tmux, returns None (subprocess fails)."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("tmux not found")
            assert get_current_session_id() is None

    def test_returns_session_name_in_tmux(self) -> None:
        """When in tmux, returns the session name."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "vibe3-executor-issue-42\n"
            result = get_current_session_id()
            assert result == "vibe3-executor-issue-42"
            mock_run.assert_called_once_with(
                ["tmux", "display-message", "-p", "#{session_name}"],
                capture_output=True,
                text=True,
                check=True,
            )


class TestGetWorktreeOwner:
    """Tests for get_worktree_owner."""

    def test_returns_none_when_no_owner(self) -> None:
        """When worktree has no registered owner, returns None."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = None

        result = get_worktree_owner(mock_store, "/path/to/worktree")
        assert result is None
        mock_store.get_worktree_owner_session.assert_called_once_with(
            "/path/to/worktree"
        )

    def test_returns_session_dict_when_owner_exists(self) -> None:
        """When worktree has a registered owner, returns session dict."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }

        result = get_worktree_owner(mock_store, "/path/to/worktree")
        assert result == {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }


class TestEnsureWorktreeOwnership:
    """Tests for ensure_worktree_ownership."""

    def test_passes_when_no_owner(self) -> None:
        """Unowned worktree allows any session."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = None

        # Should not raise
        ensure_worktree_ownership(mock_store, "/path/to/worktree")

    def test_passes_when_tmux_matches(self) -> None:
        """Matching tmux session passes."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "vibe3-executor-issue-42\n"
            # Should not raise
            ensure_worktree_ownership(mock_store, "/path/to/worktree")

    def test_raises_when_tmux_mismatches(self) -> None:
        """Different tmux session raises WorktreeOwnerMismatchError."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }
        mock_store.get_flow_state.return_value = None

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "vibe3-executor-issue-99\n"
            with pytest.raises(WorktreeOwnerMismatchError) as exc_info:
                ensure_worktree_ownership(mock_store, "/path/to/worktree")

            assert "Worktree ownership mismatch detected" in str(exc_info.value)
            assert "Current session: vibe3-executor-issue-99" in str(exc_info.value)
            assert "Owner session: vibe3-executor-issue-42" in str(exc_info.value)

    def test_raises_with_actionable_message(self) -> None:
        """Error message includes takeover instructions."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }
        mock_store.get_flow_state.return_value = None

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "vibe3-executor-issue-99\n"
            with pytest.raises(WorktreeOwnerMismatchError) as exc_info:
                ensure_worktree_ownership(mock_store, "/path/to/worktree")

            error_msg = str(exc_info.value)
            assert "vibe3 task resume --takeover" in error_msg

    def test_passes_outside_tmux(self) -> None:
        """Outside tmux (direct user), always passes."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("tmux not found")
            # Should not raise
            ensure_worktree_ownership(mock_store, "/path/to/worktree")

    def test_allows_takeover_when_requested(self) -> None:
        """When allow_takeover=True, takeover is performed."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = "vibe3-executor-issue-99\n"
            with patch(
                "vibe3.services.worktree_ownership_guard.takeover_worktree"
            ) as mock_takeover:
                # Should not raise
                ensure_worktree_ownership(
                    mock_store,
                    "/path/to/worktree",
                    allow_takeover=True,
                    takeover_reason="test",
                )

                # Verify takeover was called
                mock_takeover.assert_called_once_with(
                    mock_store,
                    "/path/to/worktree",
                    "vibe3-executor-issue-99",
                    "test",
                )


class TestTakeoverWorktree:
    """Tests for takeover_worktree."""

    def test_logs_event_and_updates_owner(self) -> None:
        """Takeover creates event and updates session binding."""
        mock_store = MagicMock()
        mock_store.get_worktree_owner_session.return_value = {
            "id": 1,
            "tmux_session": "vibe3-executor-issue-42",
            "session_name": "manager-123",
        }

        with patch("vibe3.services.signature_service.SignatureService") as mock_sig:
            mock_sig.get_worktree_actor.return_value = "test-actor"

            takeover_worktree(
                mock_store,
                "/path/to/worktree",
                "vibe3-executor-issue-99",
                "test takeover",
            )

            # Verify event was logged
            mock_store.add_event.assert_called_once()
            call_args = mock_store.add_event.call_args
            assert call_args[0][1] == "worktree_takeover"

            # Verify session was updated
            mock_store.update_runtime_session.assert_called_once_with(
                1, tmux_session="vibe3-executor-issue-99"
            )
