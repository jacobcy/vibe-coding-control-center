"""Tests for CodeagentBackend - utility functions (session_id, log_filter)."""

import subprocess
from pathlib import Path

from vibe3.agents.backends.codeagent import CodeagentBackend


class TestSessionIdExtraction:
    def test_extract_session_id_supports_modern_wrapper_format(self) -> None:
        from vibe3.agents.backends.codeagent import extract_session_id

        output = "some text\nSESSION_ID: ses_2aea4d6b6ffexDUssWC9tEP4Nh\nmore text\n"

        assert extract_session_id(output) == "ses_2aea4d6b6ffexDUssWC9tEP4Nh"

    def test_extract_session_id_supports_wrapper_json_event(self) -> None:
        from vibe3.agents.backends.codeagent import extract_session_id

        output = '{"type":"step_start","sessionID":"ses_2ae4422c7ffeYDHGar7ZxRsnTC"}'

        assert extract_session_id(output) == "ses_2ae4422c7ffeYDHGar7ZxRsnTC"

    def test_extract_session_id_supports_escaped_wrapper_json_event(self) -> None:
        from vibe3.agents.backends.codeagent import extract_session_id

        output = (
            '{"message":"{\\"type\\":\\"step_start\\",'
            '\\"sessionID\\":\\"ses_2ae0c24f2ffehx2ejWE21YTtHi\\"}"}'
        )

        assert extract_session_id(output) == "ses_2ae0c24f2ffehx2ejWE21YTtHi"


class TestAsyncLogFilter:
    def test_async_log_filter_strips_agent_prompt_block(self, tmp_path: Path) -> None:
        """Async log filter should remove <agent-prompt> blocks."""
        backend = CodeagentBackend()
        filter_cmd = backend._build_async_log_filter()

        # Create test input file
        input_file = tmp_path / "input.log"
        input_text = """SESSION_ID: ses_test123
<agent-prompt>
This is the full prompt content that should not appear in logs.
It may contain sensitive information or be very long.
</agent-prompt>
[vibe3 async] command exited with status: 0
"""
        input_file.write_text(input_text)

        # Run the filter
        result = subprocess.run(
            filter_cmd + [str(input_file)],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout

        assert "<agent-prompt>" not in output
        assert "</agent-prompt>" not in output
        assert "full prompt content" not in output
        # But should keep control info
        assert "SESSION_ID: ses_test123" in output
        assert "command exited with status: 0" in output
        # Should report suppression
        assert "suppressed" in output and "agent-prompt" in output

    def test_async_log_filter_keeps_session_id_and_exit_status_lines(
        self, tmp_path: Path
    ) -> None:
        """Filter should preserve session ID, exit status, and other diagnostics."""
        backend = CodeagentBackend()
        filter_cmd = backend._build_async_log_filter()

        input_file = tmp_path / "input.log"
        input_text = """SESSION_ID: ses_abc123
Some wrapper output line
[vibe3 async] command exited with status: 0
[vibe3 async] suppressed output summary: 150 lines
"""
        input_file.write_text(input_text)

        result = subprocess.run(
            filter_cmd + [str(input_file)],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout

        # All diagnostic lines should be preserved
        assert "SESSION_ID: ses_abc123" in output
        assert "[vibe3 async] command exited with status: 0" in output
        assert "[vibe3 async] suppressed output summary: 150 lines" in output
        assert "Some wrapper output line" in output
