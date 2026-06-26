"""Tests for audit-report governance material registration and boundaries."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.roles.governance import (
    build_governance_snapshot_context,
    load_governance_material_catalog,
)


def test_audit_report_material_is_registered() -> None:
    catalog_names = {item.name for item in load_governance_material_catalog()}

    assert "supervisor/governance/audit-report.md" in catalog_names


def test_audit_report_material_keeps_agent_led_boundary() -> None:
    content = Path("supervisor/governance/audit-report.md").read_text(encoding="utf-8")

    assert "scripts/audit-ledger-summary.py" in content
    assert ".git/shared/observations/" in content
    assert ".git/shared/suggestions/" in content
    assert ".git/shared/reports/" in content
    assert "Do not read `feedback_observations`" in content
    assert "Do not add a `vibe3 audit report` command" in content
    assert "Do not modify prompt, policy, skill, or supervisor material" in content


def test_audit_report_material_requires_frontmatter() -> None:
    """audit-report.md output format uses YAML frontmatter for machine parsing."""
    content = Path("supervisor/governance/audit-report.md").read_text(encoding="utf-8")

    assert "linked_observation_ids" in content
    assert "linked_suggestion_ids" in content
    assert "evidence_strength" in content
    assert "target_materials" in content
    assert "---" in content  # YAML frontmatter delimiter


def test_audit_report_material_requires_target_material_analysis() -> None:
    """Report must analyze original target materials, not just cluster observations."""
    content = Path("supervisor/governance/audit-report.md").read_text(encoding="utf-8")

    assert "Target Material Analysis" in content
    assert "禁止跳过此步骤直接给结论" in content
    assert "目标材料" in content or "prompt 材料" in content


def test_audit_report_material_distinguishes_suggestion_sources() -> None:
    content = Path("supervisor/governance/audit-report.md").read_text(encoding="utf-8")

    assert "runtime_observation" in content
    assert "code_auditor" in content
    assert "单条" in content and "code_auditor" in content


def test_audit_report_routing_exists() -> None:
    """audit-report.md has dedicated routing in build_governance_snapshot_context."""
    snapshot = MagicMock(
        server_running=True,
        active_flows=0,
        active_worktrees=0,
        queued_issues=(),
        circuit_breaker_state="closed",
        circuit_breaker_failures=0,
        active_issues=(),
    )

    with patch(
        "vibe3.utils.get_git_common_dir",
        return_value=str(Path("/tmp")),
    ):
        ctx = build_governance_snapshot_context(
            snapshot=snapshot,
            material_override="audit-report.md",
        )

    # Verify context has report-specific fields (not assignee-pool fallback)
    assert "observation_count" in ctx
    assert "suggestion_count" in ctx
    assert "observed_failure_modes" in ctx
    assert "material_hash" in ctx
