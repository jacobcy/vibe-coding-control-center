"""Tests for issue/spec-aware plan context building."""

from pathlib import Path

from vibe3.agents.plan_prompt import (
    _build_plan_output_contract_section,
    _build_plan_task_section,
    build_plan_prompt_body,
)
from vibe3.models import PlanRequest, PlanScope


def test_build_plan_prompt_body_includes_task_guidance() -> None:
    request = PlanRequest(
        scope=PlanScope.for_task(42),
        task_guidance="## Issue Context\nTitle: Demo issue\n\nBody text",
    )

    result = build_plan_prompt_body(request)

    assert "## Issue Context" in result
    assert "Title: Demo issue" in result
    assert "Body text" in result


def test_build_plan_prompt_body_requires_canonical_plan_and_handoff() -> None:
    request = PlanRequest(scope=PlanScope.for_task(42))

    result = build_plan_prompt_body(request)

    assert "docs/plans/" in result
    assert "handoff plan" in result


def test_build_plan_output_contract_section_keeps_output_contract_only() -> None:
    result = _build_plan_output_contract_section("Use exactly this format")

    assert result == "## Output format requirements\nUse exactly this format"


def test_build_plan_task_section_can_carry_ref_guidance() -> None:
    request = PlanRequest(scope=PlanScope.for_task(42))

    result = _build_plan_task_section(
        request,
        "Write the canonical plan under docs/plans/ and run handoff plan.",
    )

    assert "docs/plans/" in result
    assert "handoff plan" in result


def test_build_plan_prompt_body_includes_before_coding_marker_convention() -> None:
    """Plan prompt must guide planners to use REQUIRED:BEFORE_CODING markers."""
    request = PlanRequest(scope=PlanScope.for_task(42))
    result = build_plan_prompt_body(request)
    assert "REQUIRED:BEFORE_CODING" in result
    assert "Mandatory Pre-Conditions" in result


def test_build_plan_prompt_body_loads_custom_recipe(tmp_path: Path) -> None:
    """Should load custom prompt-recipes.yaml when prompts_path is provided."""
    from unittest.mock import patch

    # Create custom prompts.yaml (required by PromptAssembler)
    prompts_yaml = tmp_path / "prompts.yaml"
    prompts_yaml.write_text(
        "plan:\n  default: '{plan_prompt_body}'\n", encoding="utf-8"
    )

    # Create custom prompt-recipes.yaml with custom section key
    recipes_yaml = tmp_path / "prompt-recipes.yaml"
    recipes_yaml.write_text(
        """recipes:
  plan.default:
    template_key: plan.default
    description: Test recipe with custom section
    variants:
      first.bootstrap:
        sections:
          - custom.test_marker
""",
        encoding="utf-8",
    )

    # Create request
    request = PlanRequest(scope=PlanScope.for_task(42))

    # Mock the provider to return a custom marker
    with patch(
        "vibe3.agents.plan_prompt._build_plan_prompt_providers",
        return_value={"custom.test_marker": lambda: "CUSTOM_RECIPE_LOADED_MARKER"},
    ):
        # Build prompt with custom prompts_path
        result = build_plan_prompt_body(request, prompts_path=prompts_yaml)

    # Verify custom marker appears (proves custom recipe was loaded)
    assert "CUSTOM_RECIPE_LOADED_MARKER" in result
