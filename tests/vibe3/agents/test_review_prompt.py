"""Tests for context_builder service.

Tests both section builders (unit tests) and orchestration (integration tests).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.agents.review_prompt import (
    ContextBuilderError,
    build_ast_analysis_section,
    build_output_contract_section,
    build_policy_section,
    build_review_prompt_body,
    build_review_task_section,
    build_tools_guide_section,
)
from vibe3.models.review import ReviewRequest, ReviewScope


class TestBuildPolicySection:
    """Tests for build_policy_section (unit test)."""

    def test_reads_policy_file(self, tmp_path: Path) -> None:
        """Should read policy from file."""
        policy_file = tmp_path / "policy.md"
        policy_file.write_text("# Review Policy\n\nFocus on correctness.")

        result = build_policy_section(str(policy_file))

        assert "# Review Policy" in result
        assert "Focus on correctness" in result

    def test_raises_on_missing_file(self) -> None:
        """Should raise ContextBuilderError if file not found."""
        with pytest.raises(ContextBuilderError, match="Cannot read policy"):
            build_policy_section("/nonexistent/policy.md")


class TestBuildToolsGuideSection:
    """Tests for build_tools_guide_section (unit test)."""

    def test_returns_none_if_not_configured(self) -> None:
        """Should return None if path is None."""
        result = build_tools_guide_section(None)
        assert result is None

    def test_returns_none_if_file_not_exists(self, tmp_path: Path) -> None:
        """Should return None if file does not exist."""
        result = build_tools_guide_section(str(tmp_path / "nonexistent.md"))
        assert result is None

    def test_reads_tools_guide(self, tmp_path: Path) -> None:
        """Should read tools guide from file."""
        tools_file = tmp_path / "tools.md"
        tools_file.write_text("Use `vibe3 inspect` for analysis.")

        result = build_tools_guide_section(str(tools_file))

        assert result is not None
        assert "## Available Tools" in result
        assert "vibe3 inspect" in result


class TestBuildAstAnalysisSection:
    """Tests for build_ast_analysis_section (unit test)."""

    def test_returns_none_if_no_data(self) -> None:
        """Should return None if no symbols or DAG provided."""
        result = build_ast_analysis_section(None, None)
        assert result is None

    def test_formats_changed_symbols(self) -> None:
        """Should format changed symbols as JSON."""
        symbols = {"src/foo.py": ["func1", "func2"]}
        result = build_ast_analysis_section(symbols, None)

        assert result is not None
        assert "## AST Analysis" in result
        assert "Changed Functions" in result
        assert "func1" in result

    def test_formats_symbol_dag(self) -> None:
        """Should format symbol DAG as JSON."""
        dag = {"func1": ["caller1", "caller2"]}
        result = build_ast_analysis_section(None, dag)

        assert result is not None
        assert "Function Call Chain" in result
        assert "caller1" in result

    def test_formats_both_symbols_and_dag(self) -> None:
        """Should format both symbols and DAG."""
        symbols = {"src/foo.py": ["func1"]}
        dag = {"func1": ["caller1"]}
        result = build_ast_analysis_section(symbols, dag)

        assert "Changed Functions" in result
        assert "Function Call Chain" in result


class TestBuildReviewTaskSection:
    """Tests for build_review_task_section (unit test)."""

    def test_uses_custom_task(self) -> None:
        """Should use custom task text."""
        result = build_review_task_section("Focus on security")
        assert "## Review Task" in result
        assert "Focus on security" in result

    def test_task_section_can_carry_audit_ref_guidance(self) -> None:
        result = build_review_task_section(
            "If you write a fuller audit note, register it with handoff audit."
        )

        assert "handoff audit" in result

    def test_uses_default_task_if_none(self) -> None:
        """Should use default task if None."""
        result = build_review_task_section(None)
        assert "## Review Task" in result
        assert "git diff" in result


class TestBuildOutputContractSection:
    """Tests for build_output_contract_section (unit test)."""

    def test_uses_custom_format(self) -> None:
        """Should use custom output format."""
        result = build_output_contract_section("Custom format instructions")
        assert result == "## Output format requirements\nCustom format instructions"

    def test_uses_default_format_if_none(self) -> None:
        """Should use default format if None."""
        result = build_output_contract_section(None)
        assert "## Output format requirements" in result
        assert "VERDICT: PASS | MAJOR | BLOCK" in result


class TestBuildReviewPromptBody:
    """Tests for build_review_prompt_body orchestration (integration test)."""

    def test_build_review_prompt_body_with_ast_analysis(self) -> None:
        """Context should include AST analysis when provided."""
        with patch("vibe3.agents.review_prompt.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"

            scope = ReviewScope.for_base("main")
            request = ReviewRequest(
                scope=scope,
                changed_symbols={"src/review.py": ["build_review_prompt_body"]},
            )
            context = build_review_prompt_body(request)

        # Should include AST analysis
        assert "Changed Functions" in context
        assert "build_review_prompt_body" in context

    def test_build_review_prompt_body_includes_verdict_format(self) -> None:
        """Context should specify VERDICT output format."""
        with patch("vibe3.agents.review_prompt.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"

            scope = ReviewScope.for_base("main")
            request = ReviewRequest(scope=scope)
            context = build_review_prompt_body(request)

        assert "VERDICT:" in context
        assert "PASS" in context or "MAJOR" in context or "BLOCK" in context

    def test_build_review_prompt_body_minimal_without_ast(self) -> None:
        """Context should work without AST analysis (reviewer uses git diff)."""
        with patch("vibe3.agents.review_prompt.Path.read_text") as mock_read:
            mock_read.return_value = "# Review Policy\nTest policy content"

            scope = ReviewScope.for_base("main")
            request = ReviewRequest(scope=scope)
            context = build_review_prompt_body(request)

        # Should include policy and task guidance
        assert "Review Policy" in context
        assert "Review Task" in context
        assert "Output format requirements" in context
        # Should NOT include our internal decision metadata
        assert "core_files" not in context.lower()
        assert "risk score" not in context.lower()
        assert "total_changed" not in context.lower()

    def test_build_review_prompt_body_handles_missing_policy(self) -> None:
        """Should raise error when policy file is missing."""
        with patch("vibe3.agents.review_prompt.Path.read_text") as mock_read:
            mock_read.side_effect = OSError("File not found")

            scope = ReviewScope.for_base("main")
            request = ReviewRequest(scope=scope)

            with pytest.raises(Exception):  # ContextBuilderError
                build_review_prompt_body(request)

    def test_build_review_prompt_body_hides_internal_prompt_wiring(self) -> None:
        """Context should not leak internal file/config wiring to the agent."""
        scope = ReviewScope.for_base("main")
        request = ReviewRequest(scope=scope)

        context = build_review_prompt_body(request)

        forbidden_tokens = (
            "common.md",
            "config/settings.yaml",
            ".agent/rules",
            "Follow policy at",
        )
        for token in forbidden_tokens:
            assert token not in context

    def test_build_review_prompt_body_requires_explicit_verdict_and_audit_file(
        self,
    ) -> None:
        """Prompt should separate direct verdict output from canonical audit writing."""
        scope = ReviewScope.for_base("main")
        request = ReviewRequest(scope=scope)

        context = build_review_prompt_body(request)

        assert "The first line must be exactly:" in context
        assert "The final line must repeat the same `VERDICT:`" in context
        assert (
            "You must write a canonical audit report under `docs/reports/`" in context
        )
        assert "handoff audit" in context
