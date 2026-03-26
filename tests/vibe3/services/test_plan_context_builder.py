"""Tests for issue/spec-aware plan context building."""

from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.services.plan_context_builder import build_plan_context


def test_build_plan_context_includes_task_guidance() -> None:
    request = PlanRequest(
        scope=PlanScope.for_task(42),
        task_guidance="## Issue Context\nTitle: Demo issue\n\nBody text",
    )

    result = build_plan_context(request)

    assert "## Issue Context" in result
    assert "Title: Demo issue" in result
    assert "Body text" in result
