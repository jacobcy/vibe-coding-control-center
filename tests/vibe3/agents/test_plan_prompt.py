"""Tests for issue/spec-aware plan context building."""

from vibe3.agents.plan_prompt import (
    build_plan_output_contract_section,
    build_plan_prompt_body,
    build_plan_task_section,
)
from vibe3.models.plan import PlanRequest, PlanScope


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
    result = build_plan_output_contract_section("Use exactly this format")

    assert result == "## Output format requirements\nUse exactly this format"


def test_build_plan_task_section_can_carry_ref_guidance() -> None:
    request = PlanRequest(scope=PlanScope.for_task(42))

    result = build_plan_task_section(
        request,
        "Write the canonical plan under docs/plans/ and run handoff plan.",
    )

    assert "docs/plans/" in result
    assert "handoff plan" in result
