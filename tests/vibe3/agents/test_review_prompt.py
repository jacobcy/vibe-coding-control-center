"""Tests for context_builder service.

Tests both section builders (unit tests) and orchestration (integration tests).
"""

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.agents.review_prompt import (
    _build_ast_analysis_section,
    _build_output_contract_section,
    _build_policy_section,
    _build_review_task_section,
    build_review_prompt_body,
    describe_review_sections,
)
from vibe3.models import ReviewRequest, ReviewScope
from vibe3.prompts.exceptions import ContextBuilderError


class TestBuildPolicySection:
    """Tests for _build_policy_section (unit test)."""

    def test_reads_policy_file(self, tmp_path: Path) -> None:
        """Should read policy from file."""
        policy_file = tmp_path / "policy.md"
        policy_file.write_text("# Review Policy\n\nFocus on correctness.")

        result = _build_policy_section(str(policy_file))

        assert "# Review Policy" in result
        assert "Focus on correctness" in result

    def test_raises_on_missing_file(self) -> None:
        """Should raise ContextBuilderError if file not found."""
        with pytest.raises(ContextBuilderError, match="Cannot read policy"):
            _build_policy_section("/nonexistent/policy.md")


class TestBuildAstAnalysisSection:
    """Tests for _build_ast_analysis_section (unit test)."""

    def test_returns_none_if_no_data(self) -> None:
        """Should return None if no symbols or DAG provided."""
        result = _build_ast_analysis_section(None, None)
        assert result is None

    def test_formats_changed_symbols(self) -> None:
        """Should format changed symbols as JSON."""
        symbols = {"src/foo.py": ["func1", "func2"]}
        result = _build_ast_analysis_section(symbols, None)

        assert result is not None
        assert "## AST Analysis" in result
        assert "Changed Functions" in result
        assert "func1" in result

    def test_formats_symbol_dag(self) -> None:
        """Should format symbol DAG as JSON."""
        dag = {"func1": ["caller1", "caller2"]}
        result = _build_ast_analysis_section(None, dag)

        assert result is not None
        assert "Function Call Chain" in result
        assert "caller1" in result

    def test_formats_both_symbols_and_dag(self) -> None:
        """Should format both symbols and DAG."""
        symbols = {"src/foo.py": ["func1"]}
        dag = {"func1": ["caller1"]}
        result = _build_ast_analysis_section(symbols, dag)

        assert "Changed Functions" in result
        assert "Function Call Chain" in result


class TestBuildReviewTaskSection:
    """Tests for _build_review_task_section (unit test)."""

    def test_uses_custom_task(self) -> None:
        """Should use custom task text."""
        result = _build_review_task_section("Focus on security")
        assert "## Review Task" in result
        assert "Focus on security" in result

    def test_task_section_can_carry_audit_ref_guidance(self) -> None:
        result = _build_review_task_section(
            "If you write a fuller audit note, register it with handoff audit."
        )

        assert "handoff audit" in result

    def test_returns_empty_if_none(self) -> None:
        """Should return empty string if None."""
        result = _build_review_task_section(None)
        assert result == ""


class TestBuildOutputContractSection:
    """Tests for _build_output_contract_section (unit test)."""

    def test_uses_custom_format(self) -> None:
        """Should use custom output format."""
        result = _build_output_contract_section("Custom format instructions")
        assert result == "## Output format requirements\nCustom format instructions"

    def test_returns_empty_if_none(self) -> None:
        """Should return empty string if None."""
        result = _build_output_contract_section(None)
        assert result == ""


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
        # Verify that all standard verdict levels are present in the prompt
        for level in ["PASS", "MINOR", "MAJOR", "BLOCK", "REFUSE"]:
            assert level in context

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

            with pytest.raises(ContextBuilderError):  # ContextBuilderError
                build_review_prompt_body(request)

    def test_build_review_prompt_body_hides_internal_prompt_wiring(self) -> None:
        """Context should not leak internal file/config wiring to the agent."""
        scope = ReviewScope.for_base("main")
        request = ReviewRequest(scope=scope)

        context = build_review_prompt_body(request)

        forbidden_tokens = (
            "common.md",
            "config/settings.yaml",
            "config/v3/settings.yaml",
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

        # Check for verdict placement requirements (first and last line)
        assert re.search(r"first line.*VERDICT", context, re.IGNORECASE)
        assert re.search(r"final line.*VERDICT", context, re.IGNORECASE)

        # Check for audit reporting requirements
        assert re.search(r"audit report.*docs/reports/", context, re.IGNORECASE)
        assert "handoff audit" in context

        # Check for verdict-specific rules (e.g. PASS/REFUSE might omit audit_ref)
        assert re.search(r"PASS.*REFUSE.*omit.*audit_ref", context, re.IGNORECASE)


class TestDescribeReviewSections:
    """Tests for describe_review_sections (unit test)."""

    def test_first_bootstrap(self) -> None:
        """Should return mandatory sections for first.bootstrap variant."""
        sections = describe_review_sections("first", "bootstrap")
        assert isinstance(sections, list)
        assert len(sections) > 0
        assert all(isinstance(s, str) for s in sections)

        # Verify mandatory sections are present (behavior-based, not exact list)
        mandatory = {
            "review.policy",
            "common.rules",
            "review.output_format",
            "review.exit_contract",
        }
        assert mandatory.issubset(set(sections))

    def test_retry_bootstrap(self) -> None:
        """Should return mandatory sections for retry.bootstrap variant."""
        sections = describe_review_sections("retry", "bootstrap")
        assert isinstance(sections, list)
        assert len(sections) > 0

        # Verify mandatory sections and retry-specific section
        mandatory = {
            "review.policy",
            "review.retry_task",
            "review.output_format",
            "review.exit_contract",
        }
        assert mandatory.issubset(set(sections))

    def test_retry_resume(self) -> None:
        """Should return mandatory sections for retry.resume variant."""
        sections = describe_review_sections("retry", "resume")
        assert isinstance(sections, list)
        assert len(sections) > 0

        # Resume should at least have output_format and exit_contract for reviewer
        mandatory = {
            "review.output_format",
            "review.exit_contract",
            "review.retry_task",
        }
        assert mandatory.issubset(set(sections))

    def test_first_resume_raises(self) -> None:
        """Should raise KeyError for first.resume variant (not defined in YAML)."""
        with pytest.raises(KeyError, match="Prompt recipe variant not found"):
            describe_review_sections("first", "resume")


class TestPromptsPathRouting:
    """Tests for prompts_path parameter routing to custom manifest."""

    def test_build_review_prompt_body_loads_custom_recipe(self, tmp_path: Path) -> None:
        """Should load custom prompt-recipes.yaml when prompts_path is provided."""
        # Create custom prompts.yaml (required by PromptAssembler)
        prompts_yaml = tmp_path / "prompts.yaml"
        prompts_yaml.write_text(
            "review:\n  default: '{review_prompt_body}'\n", encoding="utf-8"
        )

        # Create custom prompt-recipes.yaml with custom section key
        recipes_yaml = tmp_path / "prompt-recipes.yaml"
        recipes_yaml.write_text(
            """recipes:
  review.default:
    template_key: review.default
    description: Test recipe with custom section
    variants:
      first.bootstrap:
        sections:
          - custom.test_marker
""",
            encoding="utf-8",
        )

        # Create request
        scope = ReviewScope.for_base("main")
        request = ReviewRequest(scope=scope)

        # Mock the provider to return a custom marker
        with patch(
            "vibe3.agents.review_prompt._build_review_prompt_providers",
            return_value={"custom.test_marker": lambda: "CUSTOM_RECIPE_LOADED_MARKER"},
        ):
            # Build prompt with custom prompts_path
            result = build_review_prompt_body(request, prompts_path=prompts_yaml)

        # Verify custom marker appears (proves custom recipe was loaded)
        assert "CUSTOM_RECIPE_LOADED_MARKER" in result
