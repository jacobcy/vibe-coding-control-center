"""Tests for ServeStatusService."""

from io import StringIO

from rich.console import Console

from vibe3.models.orchestra_config import OrchestraConfig
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


class TestResolveTickInterval:
    """Test cases for _resolve_tick_interval method."""

    def _make_service(self, polling_interval: int = 900) -> ServeStatusService:
        config = OrchestraConfig(polling_interval=polling_interval)
        return ServeStatusService(config=config)

    def test_reads_runtime_interval_from_log(self, tmp_path, monkeypatch):
        """When events.log contains [server] start tick_interval, it is used."""
        log_dir = tmp_path / "temp" / "logs" / "orchestra"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "events.log"
        log_file.write_text("[2026-05-19T10:00:00] [server] start tick_interval=30s\n")
        monkeypatch.chdir(tmp_path)

        service = self._make_service(polling_interval=900)
        assert service._resolve_tick_interval() == 30

    def test_falls_back_when_no_log(self):
        """When events.log does not exist, config default is used."""
        service = self._make_service(polling_interval=900)
        assert service._resolve_tick_interval() == 900

    def test_falls_back_when_no_start_entry(self, tmp_path, monkeypatch):
        """When events.log exists but no [server] start line, config is used."""
        log_dir = tmp_path / "temp" / "logs" / "orchestra"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "events.log"
        log_file.write_text(
            "[2026-05-19T10:00:00] [server] tick #1 start\n"
            "[2026-05-19T10:00:00] [dispatcher] something\n"
        )
        monkeypatch.chdir(tmp_path)

        service = self._make_service(polling_interval=600)
        assert service._resolve_tick_interval() == 600

    def test_uses_most_recent_start(self, tmp_path, monkeypatch):
        """When multiple [server] start entries exist, the last one is used."""
        log_dir = tmp_path / "temp" / "logs" / "orchestra"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "events.log"
        log_file.write_text(
            "[2026-05-19T08:00:00] [server] start tick_interval=60s\n"
            "[2026-05-19T09:00:00] [server] tick #1 completed\n"
            "[2026-05-19T10:00:00] [server] start tick_interval=30s\n"
        )
        monkeypatch.chdir(tmp_path)

        service = self._make_service(polling_interval=900)
        assert service._resolve_tick_interval() == 30

    def test_display_config_shows_runtime_interval(self, tmp_path, monkeypatch):
        """Integration: _display_config outputs runtime interval from log."""
        log_dir = tmp_path / "temp" / "logs" / "orchestra"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "events.log"
        log_file.write_text("[2026-05-19T10:00:00] [server] start tick_interval=45s\n")
        monkeypatch.chdir(tmp_path)

        service = self._make_service(polling_interval=900)

        # Capture console output
        string_io = StringIO()
        service.console = Console(file=string_io, force_terminal=True, width=80)
        service._display_config()

        output = string_io.getvalue()
        assert "Tick interval: 45s" in output
