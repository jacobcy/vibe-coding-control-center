"""Tests for ServeStatusService."""

from unittest.mock import MagicMock, patch

from vibe3.services.serve_status_service import ServeStatusService


class TestCleanErrorMessage:
    """Test cases for _clean_error_message static method."""

    def test_strips_codeagent_wrapper_prefix_with_exit_code_1(self):
        """Prefix with exit code 1 is stripped."""
        result = ServeStatusService._clean_error_message(
            "codeagent-wrapper failed (code 1):\nactual error"
        )
        assert result == "actual error"

    def test_strips_codeagent_wrapper_prefix_with_exit_code_2(self):
        """Prefix with exit code 2 is stripped."""
        result = ServeStatusService._clean_error_message(
            "codeagent-wrapper failed (code 2):\nsomething broke"
        )
        assert result == "something broke"

    def test_strips_tmpdir_noise(self):
        """CLAUDE_CODE_TMPDIR and everything after is removed."""
        result = ServeStatusService._clean_error_message(
            "error message CLAUDE_CODE_TMPDIR: /tmp/path other stuff"
        )
        assert result == "error message"

    def test_strips_recent_errors_suffix(self):
        """'=== Recent Errors ===' suffix is removed."""
        result = ServeStatusService._clean_error_message(
            "error message | === Recent Errors ==="
        )
        assert result == "error message"

    def test_strips_trailing_pipe(self):
        """Trailing pipe separator is removed."""
        result = ServeStatusService._clean_error_message("error message | ")
        assert result == "error message"

    def test_truncates_messages_over_100_chars(self):
        """Messages longer than 100 chars are truncated."""
        long_message = "a" * 150
        result = ServeStatusService._clean_error_message(long_message)
        assert len(result) == 100
        assert result == "a" * 100

    def test_preserves_messages_under_100_chars(self):
        """Messages under 100 chars are not modified beyond cleaning."""
        short_message = "short error message"
        result = ServeStatusService._clean_error_message(short_message)
        assert result == short_message

    def test_handles_messages_without_prefix(self):
        """Messages without codeagent-wrapper prefix are handled correctly."""
        result = ServeStatusService._clean_error_message(
            "E_MODEL_001: model error CLAUDE_CODE_TMPDIR: /tmp/path"
        )
        assert result == "E_MODEL_001: model error"

    def test_combined_cleaning_operations(self):
        """Multiple cleaning operations are applied in correct order."""
        result = ServeStatusService._clean_error_message(
            "codeagent-wrapper failed (code 1):\nactual error | "
            "CLAUDE_CODE_TMPDIR: /tmp/path | === Recent Errors ==="
        )
        assert result == "actual error"


class TestDisplayConfig:
    """Test cases for _display_config method."""

    @patch(
        "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
    )
    def test_display_config_uses_live_snapshot_when_server_running(
        self, mock_fetch_live_snapshot
    ):
        """When server is running, display shows runtime value from live snapshot."""
        from vibe3.services.orchestra_status_service import OrchestraSnapshot

        # Setup config with static value 60
        config = MagicMock()
        config.polling_interval = 60
        config.max_concurrent_flows = 3
        config.port = 8080

        # Mock live snapshot with runtime override 30
        live_snapshot = OrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            polling_interval=30,
            port=8080,
        )
        mock_fetch_live_snapshot.return_value = live_snapshot

        service = ServeStatusService(config)
        service.console = MagicMock()

        service._display_config()

        # Should show runtime value 30 with override indicator
        printed = [str(call.args[0]) for call in service.console.print.call_args_list]
        assert any(
            "30s" in msg and "(override" in msg and "60s" in msg for msg in printed
        )

    @patch(
        "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
    )
    def test_display_config_falls_back_to_static_when_server_down(
        self, mock_fetch_live_snapshot
    ):
        """When server is unreachable, display shows static config value."""
        config = MagicMock()
        config.polling_interval = 60
        config.max_concurrent_flows = 3
        config.port = 8080

        # Server unreachable
        mock_fetch_live_snapshot.return_value = None

        service = ServeStatusService(config)
        service.console = MagicMock()

        service._display_config()

        # Should show static config value without override indicator
        printed = [str(call.args[0]) for call in service.console.print.call_args_list]
        assert any("60s" in msg and "(override" not in msg for msg in printed)

    @patch(
        "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
    )
    def test_display_config_no_override_indicator_when_values_match(
        self, mock_fetch_live_snapshot
    ):
        """When live snapshot matches config, no override indicator is shown."""
        from vibe3.services.orchestra_status_service import OrchestraSnapshot

        config = MagicMock()
        config.polling_interval = 60
        config.max_concurrent_flows = 3
        config.port = 8080

        # Live snapshot has same value as config
        live_snapshot = OrchestraSnapshot(
            timestamp=1234567890.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            polling_interval=60,
            port=8080,
        )
        mock_fetch_live_snapshot.return_value = live_snapshot

        service = ServeStatusService(config)
        service.console = MagicMock()

        service._display_config()

        # Should show value without override indicator
        printed = [str(call.args[0]) for call in service.console.print.call_args_list]
        assert any("60s" in msg for msg in printed)
        assert not any("(override" in msg for msg in printed)
