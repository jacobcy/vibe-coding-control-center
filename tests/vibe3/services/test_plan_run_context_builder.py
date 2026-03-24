"""Tests for plan/run context builders."""

from pathlib import Path

from vibe3.config.settings import VibeConfig
from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.services.plan_context_builder import build_plan_context
from vibe3.services.run_context_builder import build_run_context

FORBIDDEN_INTERNAL_TOKENS = (
    "common.md",
    "config/settings.yaml",
    ".agent/rules",
    "Follow policy at",
)


def test_build_plan_context_hides_internal_prompt_wiring() -> None:
    """Plan context should expose instructions, not repo wiring details."""
    config = VibeConfig.get_defaults()
    request = PlanRequest(scope=PlanScope.for_task(123), max_steps=5)

    context = build_plan_context(request, config)

    assert "## Planning Task" in context
    for token in FORBIDDEN_INTERNAL_TOKENS:
        assert token not in context


def test_build_run_context_hides_internal_prompt_wiring(tmp_path: Path) -> None:
    """Run context should expose instructions, not repo wiring details."""
    config = VibeConfig.get_defaults()
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("## Summary\nTest plan\n", encoding="utf-8")

    context = build_run_context(str(plan_file), config)

    assert "## Execution Task" in context
    for token in FORBIDDEN_INTERNAL_TOKENS:
        assert token not in context
