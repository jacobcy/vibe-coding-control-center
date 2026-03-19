"""Tests for context_builder service.

Tests the context construction with AST-level analysis.
"""

from unittest.mock import patch

import pytest

from vibe3.services.context_builder import build_review_context


class TestBuildReviewContext:
    """Tests for build_review_context function."""

    def test_build_review_context_with_ast_analysis(self) -> None:
        """Context should include AST analysis when provided."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            changed_symbols = {
                "src/review.py": ["build_review_context", "run_inspect_json"]
            }
            context = build_review_context(changed_symbols=changed_symbols)

        # Should include AST analysis
        assert "Changed Functions" in context
        assert "build_review_context" in context
        assert "run_inspect_json" in context

    def test_build_review_context_includes_verdict_format(self) -> None:
        """Context should specify VERDICT output format."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context()

        assert "VERDICT:" in context
        assert "PASS" in context or "MAJOR" in context or "BLOCK" in context

    def test_build_review_context_minimal_without_ast(self) -> None:
        """Context should work without AST analysis (reviewer uses git diff)."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"
            context = build_review_context()

        # Should include policy and task guidance
        assert "Review Policy" in context
        assert "Review Task" in context
        assert "Output format requirements" in context
        # Should NOT include our internal decision metadata
        assert "core_files" not in context.lower()
        assert "risk score" not in context.lower()
        assert "total_changed" not in context.lower()

    def test_build_review_context_handles_missing_policy(self) -> None:
        """Should raise error when policy file is missing."""
        with patch("vibe3.services.context_builder.Path.read_text") as mock_read:
            mock_read.side_effect = OSError("File not found")

            with pytest.raises(Exception):  # ContextBuilderError
                build_review_context()
