"""Tests for audit-report governance material registration and boundaries."""

from __future__ import annotations

from pathlib import Path

from vibe3.roles.governance import load_governance_material_catalog


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
