"""Tests for context_builder service.

Tests the minimal context construction for codeagent-wrapper.
"""

from unittest.mock import patch

import pytest

from vibe3.services.context_builder import build_review_context


class TestBuildReviewContext:
    """Tests for build_review_context function."""

    def test_build_review_context_includes_required_sections(self) -> None:
        """Context should include policy, task guidance, and output format."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context()

        # Required sections
        assert "Review Policy" in context
        assert "Review Task" in context
        assert "Output format requirements" in context

    def test_build_review_context_includes_verdict_format(self) -> None:
        """Context should specify VERDICT output format."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context()

        assert "VERDICT:" in context
        assert "PASS" in context or "MAJOR" in context or "BLOCK" in context

    def test_build_review_context_is_minimal(self) -> None:
        """Context should be minimal - reviewer runs git diff themselves."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context()

        # Should NOT include our internal decision metadata
        assert "Risk Score" not in context
        assert "Impact Analysis" not in context
        assert "Impact DAG" not in context
        assert "Inspect Summary" not in context

    def test_build_review_context_handles_missing_policy(self) -> None:
        """Should raise error when policy file is missing."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.side_effect = OSError("File not found")

            with pytest.raises(Exception):  # ContextBuilderError
                build_review_context()
