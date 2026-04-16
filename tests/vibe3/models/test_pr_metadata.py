"""Tests for PRMetadata contributors property."""

from vibe3.models.pr import PRMetadata


class TestPRMetadataContributors:
    """Test suite for PRMetadata.contributors property."""

    def test_contributors_empty_returns_fallback(self) -> None:
        """When all actor fields are None, fallback to worktree user.name."""
        metadata = PRMetadata(branch="test-branch")
        contributors = metadata.contributors

        # Must not be empty per authorship standard
        assert len(contributors) > 0
        # Should be a valid actor identifier
        assert contributors[0] in ["AI Agent", "human"] or not contributors[
            0
        ].startswith("ai-")

    def test_contributors_all_placeholders_returns_fallback(self) -> None:
        """When all actors placeholders, fallback to worktree user.name."""
        metadata = PRMetadata(
            branch="test-branch",
            planner="ai-assistant",
            executor="unknown",
            reviewer="system",
            latest="ai-assistant",
        )
        contributors = metadata.contributors

        # Must not be empty per authorship standard
        assert len(contributors) > 0
        # Placeholders should be filtered out
        assert not any(c.startswith("ai-") for c in contributors)

    def test_contributors_with_real_actor(self) -> None:
        """When at least one real actor exists, use it."""
        metadata = PRMetadata(
            branch="test-branch",
            planner="claude/sonnet-4.6",
            executor=None,
            reviewer=None,
            latest="ai-assistant",
        )
        contributors = metadata.contributors

        assert len(contributors) == 1
        assert contributors[0] == "claude/sonnet-4.6"

    def test_contributors_dedup_by_backend(self) -> None:
        """Deduplicate actors by backend, keeping most specific form."""
        metadata = PRMetadata(
            branch="test-branch",
            planner="claude",
            executor="claude/sonnet-4.6",
            reviewer=None,
            latest="Agent-Claude",  # Alias that normalizes to "claude"
        )
        contributors = metadata.contributors

        # All claude variants should merge into one entry
        assert len(contributors) == 1
        # Should keep the most specific form (with model)
        assert contributors[0] == "claude/sonnet-4.6"

    def test_contributors_multiple_backends(self) -> None:
        """Handle multiple different backends."""
        metadata = PRMetadata(
            branch="test-branch",
            planner="claude/sonnet-4.6",
            executor="gemini",
            reviewer="codex",
            latest="ai-assistant",  # Placeholder, filtered out
        )
        contributors = metadata.contributors

        assert len(contributors) == 3
        # Order should match field precedence: planner, executor, reviewer
        assert contributors == ["claude/sonnet-4.6", "gemini", "codex"]

    def test_contributors_aliases_normalized(self) -> None:
        """Actor aliases should be normalized."""
        metadata = PRMetadata(
            branch="test-branch",
            planner="Agent-Claude",
            executor="claude-ai",
            reviewer=None,
            latest=None,
        )
        contributors = metadata.contributors

        # Both aliases normalize to "claude"
        assert len(contributors) == 1
        assert contributors[0] == "claude"
