"""Tests for issue/spec-aware plan context building."""

from vibe3.agents.plan_prompt import build_plan_prompt_body
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
