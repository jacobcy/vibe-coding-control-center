"""Tests for error_message_cleaner utility."""

from vibe3.utils.error_message_cleaner import (
    CODEAGENT_WRAPPER_RE,
    clean_error_message,
    compute_blocked_reason_summary,
)


class TestCleanErrorMessage:
    """Test cases for clean_error_message function."""

    def test_strips_tmpdir_noise(self):
        """CLAUDE_CODE_TMPDIR and everything after is removed."""
        result = clean_error_message(
            "error message CLAUDE_CODE_TMPDIR: /tmp/path other"
        )
        assert result == "error message"

    def test_strips_tmpdir_with_leading_space(self):
        """TMPDIR preceded by pipe and space is handled."""
        result = clean_error_message("error | CLAUDE_CODE_TMPDIR: /tmp")
        assert result == "error"

    def test_strips_recent_errors_suffix(self):
        """'=== Recent Errors ===' suffix is removed."""
        result = clean_error_message("error message | === Recent Errors ===")
        assert result == "error message"

    def test_strips_trailing_pipe(self):
        """Trailing pipe separator is removed."""
        result = clean_error_message("error message | ")
        assert result == "error message"

    def test_combined_cleaning_tmpdir_and_recent_errors(self):
        """TMPDIR and Recent Errors removed together."""
        result = clean_error_message(
            "error CLAUDE_CODE_TMPDIR: /tmp | === Recent Errors ==="
        )
        assert result == "error"

    def test_combined_cleaning_all_patterns(self):
        """All three cleaning patterns applied."""
        result = clean_error_message(
            "actual error | CLAUDE_CODE_TMPDIR: /tmp/path | === Recent Errors ==="
        )
        assert result == "actual error"

    def test_messages_without_noise_pass_through(self):
        """Clean messages are unchanged."""
        result = clean_error_message("short error message")
        assert result == "short error message"

    def test_empty_string(self):
        """Empty string returns empty string."""
        result = clean_error_message("")
        assert result == ""

    def test_whitespace_only(self):
        """Whitespace-only input returns empty string."""
        result = clean_error_message("   ")
        assert result == ""

    def test_tmpdir_at_start(self):
        """TMPDIR at the start removes everything."""
        result = clean_error_message("CLAUDE_CODE_TMPDIR: /tmp path")
        assert result == ""

    def test_codeagent_wrapper_re_constant(self):
        """CODEAGENT_WRAPPER_RE matches the expected prefix pattern."""
        assert (
            CODEAGENT_WRAPPER_RE.sub("", "codeagent-wrapper failed (code 1):\nerror")
            == "error"
        )
        assert (
            CODEAGENT_WRAPPER_RE.sub("", "codeagent-wrapper failed (code 2): something")
            == "something"
        )
        assert CODEAGENT_WRAPPER_RE.sub("", "no prefix here") == "no prefix here"


class TestCleanErrorMessageCallerDelegation:
    """Verify the shared function produces the same output as inline patterns."""

    def test_equivalent_to_inline_tmpdir_split(self):
        """clean_error_message matches inline re.split for TMPDIR."""
        import re

        message = "some error CLAUDE_CODE_TMPDIR: /tmp"
        expected = re.split(r"\s*CLAUDE_CODE_TMPDIR:", message)[0].strip()
        assert clean_error_message(message) == expected

    def test_equivalent_to_inline_recent_errors_split(self):
        """clean_error_message matches inline re.split for Recent Errors."""
        import re

        message = "some error | === Recent Errors ==="
        expected = re.split(r"\s*\|\s*=== Recent Errors ===", message)[0].strip()
        assert clean_error_message(message) == expected

    def test_equivalent_to_inline_trailing_pipe_sub(self):
        """clean_error_message matches inline re.sub for trailing pipe."""
        import re

        message = "some error | "
        expected = re.sub(r"\s*\|\s*$", "", message).strip()
        assert clean_error_message(message) == expected


class TestComputeBlockedReasonSummary:
    """Test cases for compute_blocked_reason_summary function."""

    def test_clean_short_reason_passes_through(self):
        """Short, clean reason is returned as-is."""
        result = compute_blocked_reason_summary("Simple error message")
        assert result == "Simple error message"

    def test_wrapper_prefix_stripped(self):
        """codeagent-wrapper prefix is removed."""
        result = compute_blocked_reason_summary(
            "codeagent-wrapper failed (code 1): Actual error"
        )
        assert result == "Actual error"

    def test_error_code_only_falls_back_to_next_line(self):
        """If first line only has error code, use next line."""
        result = compute_blocked_reason_summary("E_EXEC_NO_OUTPUT:\nActual error here")
        assert result == "Actual error here"

    def test_tmpdir_noise_filtered(self):
        """TMPDIR noise is removed."""
        result = compute_blocked_reason_summary(
            "Error message CLAUDE_CODE_TMPDIR: /tmp/path with more details"
        )
        assert result == "Error message"

    def test_long_message_truncated_at_sentence_boundary(self):
        """Long messages are truncated at sentence boundary."""
        long_msg = (
            "This is a very long error message that exceeds the limit. "
            "It should be truncated at the first sentence boundary."
        )
        result = compute_blocked_reason_summary(long_msg)
        assert result == "This is a very long error message that exceeds the limit."
        assert len(result) <= 80

    def test_empty_input_returns_empty_string(self):
        """Empty input returns empty string."""
        result = compute_blocked_reason_summary("")
        assert result == ""

    def test_trailing_colon_removed(self):
        """Trailing colon is removed."""
        result = compute_blocked_reason_summary("Error message:")
        assert result == "Error message"

    def test_multiline_with_code_prefix(self):
        """Multiline messages with code prefix are handled."""
        result = compute_blocked_reason_summary(
            "codeagent-wrapper failed (code 1):\nLine 1\nLine 2"
        )
        assert result == "Line 1"

    def test_short_message_without_tmpdir_unchanged(self):
        """Short messages without TMPDIR are not cleaned."""
        result = compute_blocked_reason_summary("Short error")
        assert result == "Short error"
