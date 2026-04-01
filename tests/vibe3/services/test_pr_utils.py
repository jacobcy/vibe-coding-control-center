"""Tests for PR utility functions."""

from vibe3.models.pr import PRMetadata
from vibe3.services.pr_utils import (
    _build_linked_section,
    _has_issue_linked,
    build_pr_body,
)
from vibe3.services.signature_service import SignatureService


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


class TestNormalizeActor:
    """Tests for normalize_actor."""

    def test_standard_format_passthrough(self) -> None:
        assert (
            SignatureService.normalize_actor("claude/sonnet-4.6") == "claude/sonnet-4.6"
        )

    def test_placeholder_unknown(self) -> None:
        assert SignatureService.normalize_actor("unknown") is None

    def test_placeholder_system(self) -> None:
        assert SignatureService.normalize_actor("system") is None

    def test_placeholder_server(self) -> None:
        assert SignatureService.normalize_actor("server") is None

    def test_placeholder_ai_assistant(self) -> None:
        assert SignatureService.normalize_actor("ai_assistant") is None

    def test_empty_string(self) -> None:
        assert SignatureService.normalize_actor("") is None

    def test_whitespace_only(self) -> None:
        assert SignatureService.normalize_actor("  ") is None

    def test_legacy_agent_claude(self) -> None:
        assert SignatureService.normalize_actor("Agent-Claude") == "claude"

    def test_legacy_agent_claude_lowercase(self) -> None:
        assert SignatureService.normalize_actor("agent-claude") == "claude"

    def test_legacy_agent_codex(self) -> None:
        assert SignatureService.normalize_actor("Agent-Codex") == "codex"

    def test_legacy_openai_bot(self) -> None:
        assert SignatureService.normalize_actor("openai-code-agent[bot]") == "openai"

    def test_backend_only_passthrough(self) -> None:
        assert SignatureService.normalize_actor("claude") == "claude"

    def test_strips_whitespace(self) -> None:
        assert SignatureService.normalize_actor("  claude/sonnet  ") == "claude/sonnet"


class TestContributors:
    """Tests for PRMetadata.contributors property."""

    def test_empty_when_all_none(self) -> None:
        metadata = PRMetadata()
        assert metadata.contributors == []

    def test_empty_when_all_placeholder(self) -> None:
        metadata = PRMetadata(
            planner="unknown",
            executor="system",
            reviewer="server",
            latest="ai_assistant",
        )
        assert metadata.contributors == []

    def test_dedup_after_normalization(self) -> None:
        metadata = PRMetadata(
            planner="Agent-Claude",
            executor="claude/sonnet-4.6",
            reviewer="claude-opus",
        )
        # Agent-Claude and claude/sonnet-4.6 share backend "claude",
        # the more specific form wins. claude-opus is a different backend.
        assert metadata.contributors == ["claude/sonnet-4.6", "claude-opus"]

    def test_legacy_and_standard_merge(self) -> None:
        metadata = PRMetadata(
            planner="Agent-Claude",
            executor="claude/sonnet-4.6",
        )
        assert metadata.contributors == ["claude/sonnet-4.6"]

    def test_preserves_order(self) -> None:
        metadata = PRMetadata(
            planner="codex/gpt-5.4",
            executor="claude/sonnet-4.5",
            reviewer="claude/sonnet-4.5",
            latest="codex/gpt-5.4",
        )
        assert metadata.contributors == ["codex/gpt-5.4", "claude/sonnet-4.5"]

    def test_includes_latest_actor(self) -> None:
        metadata = PRMetadata(latest="claude/sonnet-4.6")
        assert metadata.contributors == ["claude/sonnet-4.6"]

    def test_latest_deduped_with_other_roles(self) -> None:
        metadata = PRMetadata(
            planner="claude/sonnet-4.6",
            latest="claude/sonnet-4.6",
        )
        assert metadata.contributors == ["claude/sonnet-4.6"]

    def test_latest_actor_included(self) -> None:
        metadata = PRMetadata(latest="codex/gpt-5.4")
        assert metadata.contributors == ["codex/gpt-5.4"]

    def test_latest_actor_deduplicated(self) -> None:
        metadata = PRMetadata(
            planner="claude-opus",
            latest="claude-opus",
        )
        assert metadata.contributors == ["claude-opus"]


class TestBuildPrBody:
    """Tests for build_pr_body."""

    def test_no_metadata_passthrough(self) -> None:
        assert build_pr_body("plain body") == "plain body"

    def test_closes_prepended(self) -> None:
        metadata = PRMetadata(branch="f1", task_issue=42)
        result = build_pr_body("body", metadata)
        assert result.startswith("Closes #42\n\nbody")

    def test_no_duplicate_closes(self) -> None:
        metadata = PRMetadata(branch="f1", task_issue=42)
        body = "Fixes #42\n\nOriginal body"
        result = build_pr_body(body, metadata)
        assert result.startswith("Fixes #42\n\nOriginal body")

    def test_no_closes_when_task_zero(self) -> None:
        metadata = PRMetadata(branch="f1", task_issue=0)
        result = build_pr_body("body", metadata)
        assert not result.startswith("Closes")

    def test_no_contributors_section_when_all_placeholder(self) -> None:
        metadata = PRMetadata(branch="f1", planner="unknown", executor="system")
        result = build_pr_body("body", metadata)
        assert "Contributors" not in result
        assert "Vibe3 Metadata" not in result
        assert "Branch:" not in result

    def test_contributors_section_rendered(self) -> None:
        metadata = PRMetadata(
            branch="f1",
            planner="claude/sonnet-4.6",
            executor="codex/gpt-5.4",
        )
        result = build_pr_body("body", metadata)
        assert "## Contributors" in result
        assert "claude/sonnet-4.6, codex/gpt-5.4" in result

    def test_contributors_with_three_distinct(self) -> None:
        metadata = PRMetadata(
            branch="f1",
            planner="agent-a",
            executor="agent-b",
            reviewer="agent-c",
        )
        result = build_pr_body("body", metadata)
        assert "agent-a, agent-b, agent-c" in result

    def test_no_contributors_when_no_metadata(self) -> None:
        result = build_pr_body("plain body")
        assert "Contributors" not in result

    def test_closes_and_contributors_combined(self) -> None:
        metadata = PRMetadata(
            branch="f1",
            task_issue=42,
            planner="claude/sonnet-4.6",
        )
        result = build_pr_body("body", metadata)
        assert result.startswith("Closes #42\n\nbody")
        assert "## Contributors" in result
        assert "claude/sonnet-4.6" in result

    def test_idempotent_contributors(self) -> None:
        metadata = PRMetadata(
            branch="f1",
            planner="claude/sonnet-4.6",
            executor="claude/sonnet-4.6",
        )
        result = build_pr_body("body", metadata)
        assert result.count("claude/sonnet-4.6") == 1
