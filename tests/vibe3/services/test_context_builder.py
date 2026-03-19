"""Tests for context_builder service.

Tests the prompt construction for codeagent-wrapper.
"""

from unittest.mock import patch

import pytest

from vibe3.services.context_builder import build_review_context


class TestBuildReviewContext:
    """Tests for build_review_context function."""

    def test_build_review_context_includes_required_sections(self) -> None:
        """Context should include Risk Score, Impact DAG, and output format."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context(
                impact='{"symbols": ["func_a"]}',
                dag='{"nodes": ["mod_a"]}',
                score='{"score": 7, "risk_level": "HIGH"}',
            )

        # Required sections
        assert "Risk Score" in context
        assert "Impact DAG" in context
        assert "Output format requirements" in context

    def test_build_review_context_includes_verdict_format(self) -> None:
        """Context should specify VERDICT output format."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context(
                impact="{}",
                dag="{}",
                score='{"score": 5}',
            )

        assert "VERDICT:" in context
        assert "PASS" in context or "MAJOR" in context or "BLOCK" in context

    def test_build_review_context_includes_inspect_summary(self) -> None:
        """Context should include Inspect Summary section."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context(
                impact='{"changed_files": ["a.py"]}',
                dag='{"impacted_modules": ["mod_a"]}',
                score='{"score": 3, "risk_level": "LOW"}',
            )

        assert "Inspect Summary" in context

    def test_build_review_context_minimal_no_diff(self) -> None:
        """Context should work with minimal inspect-only input."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context()

        assert "Review Task" in context
        assert "Output format requirements" in context

    def test_build_review_context_handles_missing_policy(self) -> None:
        """Should raise error when policy file is missing."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.side_effect = OSError("File not found")

            with pytest.raises(Exception):  # ContextBuilderError
                build_review_context()
