"""Tests for review_parser service.

Tests the parsing of codeagent-wrapper output.
"""

from vibe3.services.review_parser import (
    ParsedReview,
    ReviewComment,
    convert_to_github_format,
    parse_codex_review,
    parse_review_output,
)


class TestParseCodexReview:
    """Tests for parse_codex_review function."""

    def test_parse_review_ignores_wrapper_preamble(self) -> None:
        """Parser should ignore wrapper preamble and extract findings."""
        raw = """
[session] started
[agent] initializing
src/vibe3/foo.py:12 [MAJOR] Missing error handling
VERDICT: BLOCK
"""
        parsed = parse_codex_review(raw)
        assert parsed.verdict == "BLOCK"
        assert len(parsed.comments) == 1
        assert parsed.comments[0].path == "src/vibe3/foo.py"

    def test_parse_review_with_absolute_path(self) -> None:
        """Parser should handle absolute paths."""
        raw = """
/Users/jacob/src/project/src/main.py:42 [CRITICAL] Security issue
VERDICT: BLOCK
"""
        parsed = parse_codex_review(raw)
        assert len(parsed.comments) == 1
        assert "main.py" in parsed.comments[0].path

    def test_parse_review_with_extra_newlines(self) -> None:
        """Parser should handle extra newlines gracefully."""
        raw = """

src/foo.py:1 [MINOR] Minor issue



VERDICT: PASS


"""
        parsed = parse_codex_review(raw)
        assert parsed.verdict == "PASS"
        assert len(parsed.comments) == 1

    def test_parse_review_with_markdown_headers(self) -> None:
        """Parser should ignore markdown headers."""
        raw = """
## Review Summary

This is a summary of the review.

src/bar.py:10 [MAJOR] Logic error

### Details
Some details here.

VERDICT: MAJOR
"""
        parsed = parse_codex_review(raw)
        assert parsed.verdict == "MAJOR"
        assert len(parsed.comments) == 1

    def test_parse_review_default_pass(self) -> None:
        """Parser should default to PASS when no VERDICT found."""
        raw = """
src/baz.py:5 [MINOR] Code style issue
"""
        parsed = parse_codex_review(raw)
        assert parsed.verdict == "PASS"

    def test_parse_review_multiple_comments(self) -> None:
        """Parser should extract multiple comments."""
        raw = """
src/a.py:10 [MAJOR] Issue 1
src/b.py:20 [CRITICAL] Issue 2
src/c.py:30 [MINOR] Issue 3
VERDICT: BLOCK
"""
        parsed = parse_codex_review(raw)
        assert len(parsed.comments) == 3
        assert parsed.comments[0].severity == "MAJOR"
        assert parsed.comments[1].severity == "CRITICAL"
        assert parsed.comments[2].severity == "MINOR"

    def test_parse_review_empty_output(self) -> None:
        """Parser should handle empty output."""
        parsed = parse_codex_review("")
        assert parsed.verdict == "PASS"
        assert len(parsed.comments) == 0

    def test_parse_review_wrapper_logs(self) -> None:
        """Parser should ignore wrapper log lines."""
        raw = """
[2024-03-19 10:00:00] INFO: Starting review
[2024-03-19 10:00:01] DEBUG: Processing file: foo.py
src/foo.py:100 [MAJOR] Bug found
[2024-03-19 10:00:02] INFO: Review complete
VERDICT: MAJOR
"""
        parsed = parse_codex_review(raw)
        assert parsed.verdict == "MAJOR"
        assert len(parsed.comments) == 1

    def test_parse_review_output_alias(self) -> None:
        """parse_review_output should be an alias for parse_codex_review."""
        raw = "src/foo.py:10 [MAJOR] Issue\nVERDICT: MAJOR"
        parsed = parse_review_output(raw)
        assert parsed.verdict == "MAJOR"
        assert len(parsed.comments) == 1


class TestReviewComment:
    """Tests for ReviewComment model."""

    def test_comment_creation(self) -> None:
        """Should create comment with correct attributes."""
        comment = ReviewComment(
            path="src/foo.py",
            line=42,
            severity="MAJOR",
            body="Missing error handling",
        )
        assert comment.path == "src/foo.py"
        assert comment.line == 42
        assert comment.severity == "MAJOR"
        assert comment.body == "Missing error handling"


class TestParsedReview:
    """Tests for ParsedReview model."""

    def test_parsed_review_creation(self) -> None:
        """Should create parsed review with correct attributes."""
        comments = [ReviewComment(path="a.py", line=1, severity="MAJOR", body="issue")]
        review = ParsedReview(comments=comments, verdict="MAJOR", raw="raw output")
        assert review.verdict == "MAJOR"
        assert len(review.comments) == 1
        assert review.raw == "raw output"


class TestConvertToGithubFormat:
    """Tests for convert_to_github_format function."""

    def test_convert_single_comment(self) -> None:
        """Should convert single comment to GitHub format."""
        review = ParsedReview(
            comments=[
                ReviewComment(
                    path="src/foo.py", line=42, severity="MAJOR", body="Issue"
                )
            ],
            verdict="MAJOR",
            raw="raw",
        )
        github_comments = convert_to_github_format(review)
        assert len(github_comments) == 1
        assert github_comments[0]["path"] == "src/foo.py"
        assert github_comments[0]["line"] == 42
        assert "**[MAJOR]**" in github_comments[0]["body"]  # type: ignore
        assert github_comments[0]["side"] == "RIGHT"  # type: ignore

    def test_convert_empty_comments(self) -> None:
        """Should return empty list for no comments."""
        review = ParsedReview(comments=[], verdict="PASS", raw="raw")
        github_comments = convert_to_github_format(review)
        assert github_comments == []

    def test_convert_multiple_comments(self) -> None:
        """Should convert multiple comments."""
        review = ParsedReview(
            comments=[
                ReviewComment(path="a.py", line=1, severity="MAJOR", body="i1"),
                ReviewComment(path="b.py", line=2, severity="CRITICAL", body="i2"),
            ],
            verdict="BLOCK",
            raw="raw",
        )
        github_comments = convert_to_github_format(review)
        assert len(github_comments) == 2
