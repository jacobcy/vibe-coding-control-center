"""Tests for PromptValidationService."""

from pathlib import Path

import pytest

from vibe3.prompts.models import PromptRecipe, PromptVariableSource, VariableSourceKind
from vibe3.prompts.validation import (
    PromptValidationResult,
    PromptValidationService,
    ValidationIssue,
)


def _literal_source(value: str) -> PromptVariableSource:
    return PromptVariableSource(kind=VariableSourceKind.LITERAL, value=value)


def _provider_source(key: str) -> PromptVariableSource:
    return PromptVariableSource(kind=VariableSourceKind.PROVIDER, provider=key)


def _file_source(path: str) -> PromptVariableSource:
    return PromptVariableSource(kind=VariableSourceKind.FILE, path=path)


class TestPromptValidationResult:
    def test_is_frozen(self) -> None:
        result = PromptValidationResult(
            template_key="run.plan",
            is_valid=True,
            issues=(),
            preview_text=None,
            provenance=None,
        )
        with pytest.raises((AttributeError, TypeError)):
            result.is_valid = False  # type: ignore[misc]

    def test_valid_result_has_no_issues(self) -> None:
        result = PromptValidationResult(
            template_key="run.plan",
            is_valid=True,
            issues=(),
            preview_text="hello",
            provenance=(),
        )
        assert result.is_valid
        assert result.issues == ()


class TestValidationIssue:
    def test_is_frozen(self) -> None:
        issue = ValidationIssue(kind="missing_template", message="not found")
        with pytest.raises((AttributeError, TypeError)):
            issue.kind = "other"  # type: ignore[misc]


class TestPromptValidationServiceTemplateKey:
    def test_unknown_template_key_returns_invalid(self, tmp_path: Path) -> None:
        svc = PromptValidationService(prompts_path=tmp_path / "nonexistent.yaml")
        result = svc.validate_template_key("does.not.exist")
        assert not result.is_valid
        assert any(i.kind == "missing_template" for i in result.issues)

    def test_valid_template_key_returns_valid(self) -> None:
        """run.plan is a known default template key."""
        svc = PromptValidationService()
        result = svc.validate_template_key("run.plan")
        assert result.is_valid
        assert result.issues == ()

    def test_validate_lists_required_variables(self) -> None:
        """validate_template_key should report variables required by the template."""
        svc = PromptValidationService()
        result = svc.validate_template_key("run.plan")
        assert result.required_variables == {"run_prompt_body"}

    def test_orchestra_governance_template_key(self) -> None:
        svc = PromptValidationService()
        result = svc.validate_template_key("orchestra.governance.plan")
        assert result.is_valid
        assert "supervisor_name" in result.required_variables
        assert "supervisor_content" in result.required_variables


class TestPromptValidationServiceRenderSample:
    def test_render_sample_with_literal_sources(self) -> None:
        svc = PromptValidationService()
        recipe = PromptRecipe(
            template_key="orchestra.assignee_dispatch.manager",
            variables={
                "issue_number": _literal_source("42"),
                "issue_title": _literal_source("Fix the bug"),
            },
        )
        result = svc.render_sample(recipe)
        assert result.is_valid
        assert result.preview_text is not None
        assert "42" in result.preview_text
        assert "Fix the bug" in result.preview_text
        assert result.provenance is not None

    def test_render_sample_provider_uses_placeholder(self) -> None:
        """PROVIDER sources get a placeholder value when no registry entry exists."""
        svc = PromptValidationService()
        recipe = PromptRecipe(
            template_key="run.plan",
            variables={
                "run_prompt_body": _provider_source("run.context"),
            },
        )
        result = svc.render_sample(recipe)
        assert result.is_valid
        assert result.preview_text is not None
        assert "<provider:run.context>" in result.preview_text

    def test_render_sample_missing_variable_returns_invalid(self) -> None:
        """Recipe missing a variable required by template gives invalid result."""
        svc = PromptValidationService()
        recipe = PromptRecipe(
            template_key="run.plan",
            variables={},  # run_prompt_body not declared
        )
        result = svc.render_sample(recipe)
        assert not result.is_valid
        assert any(i.kind == "missing_variable" for i in result.issues)

    def test_render_sample_file_not_found_is_reported(self, tmp_path: Path) -> None:
        """FILE source pointing to missing file produces a validation issue."""
        svc = PromptValidationService()
        recipe = PromptRecipe(
            template_key="run.plan",
            variables={
                "run_prompt_body": _file_source(str(tmp_path / "nonexistent.md")),
            },
        )
        result = svc.render_sample(recipe)
        # File not found doesn't prevent render (returns ""), but reports an issue
        assert any(i.kind == "file_not_found" for i in result.issues)

    def test_render_sample_existing_file_is_included(self, tmp_path: Path) -> None:
        content = "# My Plan\n\n## Tasks\n- Do stuff"
        plan_file = tmp_path / "plan.md"
        plan_file.write_text(content, encoding="utf-8")
        svc = PromptValidationService()
        recipe = PromptRecipe(
            template_key="run.plan",
            variables={
                "run_prompt_body": _file_source(str(plan_file)),
            },
        )
        result = svc.render_sample(recipe)
        assert result.is_valid
        assert result.preview_text is not None
        assert "My Plan" in result.preview_text

    def test_unknown_template_key_in_render_sample_returns_invalid(self) -> None:
        svc = PromptValidationService()
        recipe = PromptRecipe(
            template_key="does.not.exist",
            variables={},
        )
        result = svc.render_sample(recipe)
        assert not result.is_valid
        assert any(i.kind == "missing_template" for i in result.issues)
