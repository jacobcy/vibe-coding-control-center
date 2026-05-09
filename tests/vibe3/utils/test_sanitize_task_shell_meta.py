"""Tests for sanitize_task_shell_meta function."""

from vibe3.utils.codeagent_helpers import sanitize_task_shell_meta


class TestSanitizeTaskShellMeta:
    """Test shell meta character sanitization."""

    def test_glob_characters(self) -> None:
        """Test shell glob characters are replaced."""
        assert sanitize_task_shell_meta("*") == "×"
        assert sanitize_task_shell_meta("?") == "？"
        assert sanitize_task_shell_meta("[") == "【"
        assert sanitize_task_shell_meta("]") == "】"
        assert sanitize_task_shell_meta("{") == "｛"
        assert sanitize_task_shell_meta("}") == "｝"

    def test_special_characters(self) -> None:
        """Test shell special characters are replaced."""
        assert sanitize_task_shell_meta("\\") == "＼"
        assert sanitize_task_shell_meta('"') == "＂"
        assert sanitize_task_shell_meta("'") == "＇"
        assert sanitize_task_shell_meta("`") == "｀"
        assert sanitize_task_shell_meta("$") == "＄"

    def test_newline_replaced_with_space(self) -> None:
        """Test newline is replaced with space."""
        assert sanitize_task_shell_meta("line1\nline2") == "line1 line2"
        assert sanitize_task_shell_meta("\n") == " "

    def test_combined_special_characters(self) -> None:
        """Test multiple special characters in one string."""
        # Issue #409 directive example
        task = 'if verbose == 0 and "verbose" in ctx.meta:'
        result = sanitize_task_shell_meta(task)
        assert "＂" in result  # Double quote replaced
        assert '"' not in result  # No original quote

    def test_shell_command_with_dollar(self) -> None:
        """Test shell command with dollar sign."""
        task = "echo $HOME"
        result = sanitize_task_shell_meta(task)
        assert result == "echo ＄HOME"

    def test_backtick_command(self) -> None:
        """Test backtick command substitution."""
        task = "ls `pwd`"
        result = sanitize_task_shell_meta(task)
        assert result == "ls ｀pwd｀"

    def test_path_with_backslash(self) -> None:
        """Test Windows-style path with backslash."""
        task = "path\\to\\file"
        result = sanitize_task_shell_meta(task)
        assert result == "path＼to＼file"

    def test_multiline_task(self) -> None:
        """Test multiline task description."""
        task = "Line 1\nLine 2\nLine 3"
        result = sanitize_task_shell_meta(task)
        assert result == "Line 1 Line 2 Line 3"
        assert "\n" not in result

    def test_complex_issue_409_directive(self) -> None:
        """Test complex directive from issue #409."""
        task = """# Executor Fix Directive: Issue #409

## Problem
The guard uses `if verbose == 0` and "verbose" in ctx.meta:

```python
if verbose == 0 and "verbose" in ctx.meta:
```

Run: `vibe3 -vvv serve start`
"""
        result = sanitize_task_shell_meta(task)
        # Should not contain any trigger characters
        assert "\n" not in result
        assert "\\" not in result
        assert '"' not in result
        assert "'" not in result
        assert "`" not in result
        assert "$" not in result
        # Should contain replacement characters
        assert "＂" in result  # Double quote
        assert "｀" in result  # Backtick

    def test_no_special_characters(self) -> None:
        """Test string without special characters."""
        task = "Simple task description"
        result = sanitize_task_shell_meta(task)
        assert result == task

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert sanitize_task_shell_meta("") == ""

    def test_preserves_unicode(self) -> None:
        """Test that existing unicode characters are preserved."""
        task = "中文描述 × ？"
        result = sanitize_task_shell_meta(task)
        assert "中文描述" in result
