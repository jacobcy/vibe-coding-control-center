"""Tests for plan/run context builders."""

from pathlib import Path

from vibe3.agents.plan_prompt import build_plan_prompt_body
from vibe3.agents.run_prompt import (
    build_run_output_contract_section,
    build_run_prompt_body,
    build_run_task_section,
)
from vibe3.config.settings import VibeConfig
from vibe3.models.plan import PlanRequest, PlanScope

FORBIDDEN_INTERNAL_TOKENS = (
    "common.md",
    "config/settings.yaml",
    "config/v3/settings.yaml",
    ".agent/rules",
    "Follow policy at",
)


def test_build_plan_prompt_body_hides_internal_prompt_wiring() -> None:
    """Plan context should expose instructions, not repo wiring details."""
    config = VibeConfig.get_defaults()
    request = PlanRequest(scope=PlanScope.for_task(123), max_steps=5)

    context = build_plan_prompt_body(request, config)

    assert "## Planning Task" in context
    for token in FORBIDDEN_INTERNAL_TOKENS:
        assert token not in context


def test_build_run_prompt_body_hides_internal_prompt_wiring(tmp_path: Path) -> None:
    """Run context should expose instructions, not repo wiring details."""
    config = VibeConfig.get_defaults()
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("## Summary\nTest plan\n", encoding="utf-8")

    context = build_run_prompt_body(str(plan_file), config)

    assert "## Execution Task" in context
    for token in FORBIDDEN_INTERNAL_TOKENS:
        assert token not in context


def test_build_run_prompt_body_requires_report_ref_registration(tmp_path: Path) -> None:
    config = VibeConfig.get_defaults()
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("## Summary\nTest plan\n", encoding="utf-8")

    context = build_run_prompt_body(str(plan_file), config)

    assert "docs/reports/" in context
    assert "handoff report" in context


def test_build_run_prompt_body_instructs_ref_reads_via_handoff_show(
    tmp_path: Path,
) -> None:
    config = VibeConfig.get_defaults()
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("## Summary\nTest plan\n", encoding="utf-8")

    context = build_run_prompt_body(str(plan_file), config)

    assert "handoff show <ref>" in context
    assert "Do not call file-reading tools directly" in context


def test_build_run_prompt_body_retry_mode_uses_retry_task(tmp_path: Path) -> None:
    config = VibeConfig.get_defaults()
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("## Summary\nFix round\n", encoding="utf-8")

    context = build_run_prompt_body(str(plan_file), config, mode="retry")

    assert "focused retry round" in context
    assert "Follow plan steps strictly" not in context


def test_build_run_prompt_body_retry_resume_mode_is_minimal(tmp_path: Path) -> None:
    config = VibeConfig.get_defaults()
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("## Summary\nRetry round\n", encoding="utf-8")

    context = build_run_prompt_body(
        str(plan_file),
        config,
        audit_file=str(tmp_path / "audit.md"),
        mode="retry",
        context_mode="resume",
    )

    assert "focused retry round" in context
    assert "## Implementation Plan" not in context


def test_build_run_output_contract_section_keeps_output_contract_only() -> None:
    result = build_run_output_contract_section("Use exactly this report format")

    assert result == "## Output format requirements\nUse exactly this report format"


def test_build_run_task_section_can_carry_report_ref_guidance() -> None:
    result = build_run_task_section(
        "Write the canonical report under docs/reports/ and run handoff report."
    )

    assert "docs/reports/" in result
    assert "handoff report" in result
