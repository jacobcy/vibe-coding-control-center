"""Test orchestra logging functions."""

from vibe3.observability.orchestra_log import orchestra_events_log_path


class TestOrchestraLogging:
    """Test orchestra logging path resolution."""

    def test_orchestra_events_log_path_returns_main_repo_path(self):
        """orchestra_events_log_path should return path in main repository."""
        log_path = orchestra_events_log_path()

        # Should be an absolute path
        assert log_path.is_absolute()

        # Should not contain .worktrees (should be main repo path)
        assert ".worktrees" not in str(log_path)

        # Should end with temp/logs/orchestra/events.log
        assert str(log_path).endswith("temp/logs/orchestra/events.log")

        # Parent directory should exist (orchestra_events_log_path creates it)
        assert log_path.parent.exists()
