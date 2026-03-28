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


class TestContributors:
    """Tests for PRMetadata.contributors property."""

    def test_empty_when_all_none(self) -> None:
        metadata = PRMetadata()
        assert metadata.contributors == []

    def test_empty_when_all_default(self) -> None:
        metadata = PRMetadata(planner="unknown", executor="system", reviewer="server")
        assert metadata.contributors == []

    def test_filters_and_deduplicates(self) -> None:
        metadata = PRMetadata(
            planner="claude-opus",
            executor="claude-opus",  # duplicate
            reviewer="system",  # default
        )
        assert metadata.contributors == ["claude-opus"]

    def test_preserves_order(self) -> None:
        metadata = PRMetadata(
            planner="codex/gpt-5.4",
            executor="claude/sonnet-4.5",
            reviewer="claude/sonnet-4.5",  # duplicate
        )
        assert metadata.contributors == ["codex/gpt-5.4", "claude/sonnet-4.5"]

    def test_case_insensitive_default_filter(self) -> None:
        metadata = PRMetadata(planner="Unknown", executor="System")
        assert metadata.contributors == []

    def test_empty_string_filtered(self) -> None:
        metadata = PRMetadata(planner="", executor="claude-opus")
        assert metadata.contributors == ["claude-opus"]


class TestBuildPrBodyContributors:
    """Tests for contributors section in build_pr_body."""

    def test_no_contributors_section_when_all_default(self) -> None:
        metadata = PRMetadata(branch="f1", planner="unknown", executor="system")
        result = build_pr_body("body", metadata)
        assert "Contributors" not in result

    def test_contributors_section_rendered(self) -> None:
        metadata = PRMetadata(
            branch="f1",
            planner="claude-opus",
            executor="claude-sonnet",
        )
        result = build_pr_body("body", metadata)
        assert "**Contributors:** claude-opus, claude-sonnet" in result

    def test_contributors_with_three_distinct(self) -> None:
        metadata = PRMetadata(
            branch="f1",
            planner="agent-a",
            executor="agent-b",
            reviewer="agent-c",
        )
        result = build_pr_body("body", metadata)
        assert "**Contributors:** agent-a, agent-b, agent-c" in result

    def test_idempotent_no_duplicate_block(self) -> None:
        metadata = PRMetadata(
            branch="f1",
            planner="claude-opus",
            executor="claude-opus",
        )
        result = build_pr_body("body", metadata)
        count = result.count("Contributors")
        assert count == 1

    def test_no_contributors_when_no_metadata(self) -> None:
        result = build_pr_body("plain body")
        assert "Contributors" not in result

    def test_reviewer_in_metadata_section(self) -> None:
        metadata = PRMetadata(branch="f1", reviewer="claude-opus")
        result = build_pr_body("body", metadata)
        assert "**Reviewer:** claude-opus" in result
