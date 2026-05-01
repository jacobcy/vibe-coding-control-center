"""Tests for issue reference parsing utilities."""

import pytest

from vibe3.utils.issue_ref import parse_issue_number, try_parse_issue_number


class TestParseIssueNumber:
    """Tests for parse_issue_number function."""

    def test_plain_number(self) -> None:
        """Plain number should be parsed."""
        assert parse_issue_number("123") == 123

    def test_hash_number(self) -> None:
        """#123 format should be parsed."""
        assert parse_issue_number("#123") == 123

    def test_github_url(self) -> None:
        """GitHub issue URL should be parsed."""
        assert parse_issue_number("https://github.com/owner/repo/issues/456") == 456

    def test_github_url_with_query(self) -> None:
        """GitHub issue URL with query params should be parsed."""
        url = "https://github.com/owner/repo/issues/456?query=1"
        assert parse_issue_number(url) == 456

    def test_invalid_format(self) -> None:
        """Invalid format should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid issue format"):
            parse_issue_number("invalid")

    def test_hash_with_trailing_chars(self) -> None:
        """#123abc should raise ValueError (strict parsing)."""
        with pytest.raises(ValueError, match="Invalid issue format"):
            parse_issue_number("#123abc")


class TestTryParseIssueNumber:
    """Tests for try_parse_issue_number function."""

    def test_plain_number(self) -> None:
        """Plain number should be parsed."""
        assert try_parse_issue_number("123") == 123

    def test_hash_number(self) -> None:
        """#123 format should be parsed."""
        assert try_parse_issue_number("#123") == 123

    def test_github_url(self) -> None:
        """GitHub issue URL should be parsed."""
        assert try_parse_issue_number("https://github.com/owner/repo/issues/456") == 456

    def test_github_url_with_query(self) -> None:
        """GitHub issue URL with query params should be parsed."""
        url = "https://github.com/owner/repo/issues/456?query=1"
        assert try_parse_issue_number(url) == 456

    def test_invalid_format_returns_none(self) -> None:
        """Invalid format should return None."""
        assert try_parse_issue_number("invalid") is None

    def test_hash_with_trailing_chars_returns_none(self) -> None:
        """#123abc should return None (strict parsing)."""
        assert try_parse_issue_number("#123abc") is None
