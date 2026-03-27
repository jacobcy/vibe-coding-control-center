"""Tests for PR utility functions."""

from vibe3.models.pr import PRMetadata
from vibe3.services.pr_utils import (
    _build_linked_section,
    _has_issue_linked,
    build_pr_body,
)


class TestHasIssueLinked:
    """Tests for _has_issue_linked."""

    def test_detects_closes_keyword(self) -> None:
        assert _has_issue_linked("Closes #42", 42) is True

    def test_detects_fixes_keyword(self) -> None:
        assert _has_issue_linked("Fixes #42", 42) is True

    def test_detects_resolves_keyword(self) -> None:
        assert _has_issue_linked("Resolves #42", 42) is True

    def test_case_insensitive(self) -> None:
        assert _has_issue_linked("CLOSES #42", 42) is True
        assert _has_issue_linked("fixes #42", 42) is True

    def test_closed_variant(self) -> None:
        assert _has_issue_linked("Closed #42", 42) is True

    def test_fixed_variant(self) -> None:
        assert _has_issue_linked("Fixed #42", 42) is True

    def test_no_match_different_issue(self) -> None:
        assert _has_issue_linked("Closes #99", 42) is False

    def test_no_match_no_keyword(self) -> None:
        assert _has_issue_linked("Task Issue: #42", 42) is False

    def test_empty_body(self) -> None:
        assert _has_issue_linked("", 42) is False

    def test_none_body(self) -> None:
        assert _has_issue_linked(None, 42) is False  # type: ignore[arg-type]

    def test_keyword_mid_body(self) -> None:
        assert _has_issue_linked("some text\nCloses #42\nmore text", 42) is True


class TestBuildLinkedSection:
    """Tests for _build_linked_section."""

    def test_no_task_issue(self) -> None:
        metadata = PRMetadata(branch="main", task_issue=None)
        assert _build_linked_section(metadata, "body") == ""

    def test_injects_closes_when_new(self) -> None:
        metadata = PRMetadata(branch="main", task_issue=42)
        result = _build_linked_section(metadata, "body")
        assert result == "Closes #42\n\n"

    def test_skips_when_already_linked(self) -> None:
        metadata = PRMetadata(branch="main", task_issue=42)
        body = "Closes #42 already here"
        assert _build_linked_section(metadata, body) == ""

    def test_skips_when_linked_with_fixes(self) -> None:
        metadata = PRMetadata(branch="main", task_issue=42)
        body = "Fixes #42"
        assert _build_linked_section(metadata, body) == ""


class TestBuildPrBody:
    """Tests for build_pr_body."""

    def test_no_metadata_passthrough(self) -> None:
        assert build_pr_body("plain body") == "plain body"

    def test_metadata_appended(self) -> None:
        metadata = PRMetadata(branch="feature-1", task_issue=None)
        result = build_pr_body("body", metadata)
        assert result.startswith("body")
        assert "**Branch:** feature-1" in result

    def test_task_issue_injected_at_top(self) -> None:
        metadata = PRMetadata(branch="feature-1", task_issue=42)
        result = build_pr_body("body", metadata)
        assert result.startswith("Closes #42\n\nbody")
        assert "**Task Issue:** #42" in result

    def test_no_duplicate_linking_keyword(self) -> None:
        metadata = PRMetadata(branch="feature-1", task_issue=42)
        body = "Fixes #42\n\nOriginal body"
        result = build_pr_body(body, metadata)
        # Should not prepend another Closes/Fixes
        assert result.startswith("Fixes #42\n\nOriginal body")
        # Count occurrences of linking keywords for #42
        count = result.count("#42")
        assert count == 2  # one in body, one in metadata section

    def test_task_issue_only_in_metadata_when_zero(self) -> None:
        metadata = PRMetadata(branch="feature-1", task_issue=0)
        result = build_pr_body("body", metadata)
        assert not result.startswith("Closes")
