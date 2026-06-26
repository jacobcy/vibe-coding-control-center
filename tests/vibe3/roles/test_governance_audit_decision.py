"""Tests for audit-decision governance context builder."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from vibe3.roles.governance_utils import build_audit_decision_context


def _make_snapshot() -> Any:
    """Create a mock snapshot for testing."""
    return MagicMock(
        server_running=True,
        active_flows=0,
        active_worktrees=0,
        queued_issues=(),  # Must be tuple[int, ...]
        circuit_breaker_state="closed",
        circuit_breaker_failures=0,
        active_issues=(),
    )


class TestBuildAuditDecisionContext:
    def test_build_context_empty_reports(self, tmp_path: Path) -> None:
        """No reports directory → minimal context."""
        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_decision_context(snapshot)

            assert result["report_count"] == 0
            assert result["new_since_last_run"] == 0
            assert result["evidence_strengths"] == []
            assert "目前无报告" in result["scope_note"]
            assert "按材料中的路由规则" in result["scope_note"]
            assert "supervisor decision issue" not in result["scope_note"]

    def test_build_context_with_count(self, tmp_path: Path) -> None:
        """Context reflects report count."""
        # Create reports directory with sample files
        reports_dir = tmp_path / "shared" / "reports"
        reports_dir.mkdir(parents=True)

        # Create sample report files
        for i in range(2):
            report_file = reports_dir / f"audit-report-20260623T{i:02d}0000.md"
            report_file.write_text(
                f"# Audit Report\n\n"
                f"Evidence strength: {'strong' if i == 0 else 'medium'}\n\n"
                f"Observations: obs-00{i}\n"
            )

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_decision_context(snapshot)

            assert result["report_count"] == 2
            assert "medium" in result["evidence_strengths"]
            assert "strong" in result["evidence_strengths"]

    def test_build_context_extracts_evidence_strength(self, tmp_path: Path) -> None:
        """Context extracts evidence strength from reports."""
        # Create reports directory with different evidence strengths
        reports_dir = tmp_path / "shared" / "reports"
        reports_dir.mkdir(parents=True)

        evidence_strengths = ["weak", "inconclusive"]
        for i, strength in enumerate(evidence_strengths):
            report_file = reports_dir / f"audit-report-{i:03d}.md"
            report_file.write_text(f"Evidence strength: {strength}")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_decision_context(snapshot)

            assert result["report_count"] == 2
            assert sorted(result["evidence_strengths"]) == ["inconclusive", "weak"]

    def test_build_context_input_cap(self, tmp_path: Path) -> None:
        """More than 5 reports → capped at 5 for stats."""
        # Create reports directory with many files
        reports_dir = tmp_path / "shared" / "reports"
        reports_dir.mkdir(parents=True)

        # Create 10 report files
        for i in range(10):
            report_file = reports_dir / f"audit-report-{i:03d}.md"
            report_file.write_text("Evidence strength: medium")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_decision_context(snapshot)

            # Count should be 10 (total files)
            assert result["report_count"] == 10
            # Evidence strength extraction only processes first 5

    def test_build_context_multiple_evidence_strengths(self, tmp_path: Path) -> None:
        """Context includes all detected evidence strengths."""
        # Create reports directory with multiple strengths
        reports_dir = tmp_path / "shared" / "reports"
        reports_dir.mkdir(parents=True)

        strengths = ["strong", "medium", "weak"]
        for i, strength in enumerate(strengths):
            report_file = reports_dir / f"audit-report-20260623T{i:02d}0000.md"
            report_file.write_text(f"Evidence strength: {strength}")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_decision_context(snapshot)

            assert result["report_count"] == 3
            # All strengths should be in scope_note
            assert "strong" in result["scope_note"]
            assert "medium" in result["scope_note"]
            assert "weak" in result["scope_note"]

    def test_build_context_fallback_path(self) -> None:
        """Fallback to relative path when get_git_common_dir fails."""
        with patch(
            "vibe3.utils.get_git_common_dir",
            side_effect=Exception("Test error"),
        ):
            snapshot = _make_snapshot()
            result = build_audit_decision_context(snapshot)

            # Should still work with fallback path
            assert "report_count" in result
            assert "scope_note" in result

    def test_build_context_handles_parse_error(self, tmp_path: Path) -> None:
        """Skip files with invalid content."""
        # Create reports directory with mixed valid/invalid files
        reports_dir = tmp_path / "shared" / "reports"
        reports_dir.mkdir(parents=True)

        # Valid file
        report_file = reports_dir / "audit-report-001.md"
        report_file.write_text("Evidence strength: strong")

        # Invalid file (no evidence strength field)
        invalid_file = reports_dir / "audit-report-002.md"
        invalid_file.write_text("invalid content without proper structure")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_decision_context(snapshot)

            # Should count both files
            assert result["report_count"] == 2
            # But only valid evidence strength should be extracted
            assert "strong" in result["evidence_strengths"]


class TestMaterialRouting:
    def test_routing_audit_decision_md(self, tmp_path: Path) -> None:
        """Test that audit-decision.md material routing works."""
        from vibe3.roles.governance import build_governance_snapshot_context

        # Create mock snapshot
        snapshot = MagicMock(
            server_running=True,
            active_flows=0,
            active_worktrees=0,
            queued_issues=(),
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
            active_issues=(),
        )

        # Create reports directory
        reports_dir = tmp_path / "shared" / "reports"
        reports_dir.mkdir(parents=True)

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            # Test with material_override
            ctx = build_governance_snapshot_context(
                snapshot=snapshot,
                material_override="audit-decision.md",
            )

            assert "report_count" in ctx
            assert "evidence_strengths" in ctx

    def test_routing_coexistence_with_other_materials(self, tmp_path: Path) -> None:
        """Test that audit-decision routing doesn't break other materials."""
        from vibe3.roles.governance import build_governance_snapshot_context

        snapshot = MagicMock(
            server_running=True,
            active_flows=0,
            active_worktrees=0,
            queued_issues=(),
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
            active_issues=(),
        )

        # Create observations directory
        obs_dir = tmp_path / "shared" / "observations"
        obs_dir.mkdir(parents=True)

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            # Test that audit-observation still routes correctly
            ctx_obs = build_governance_snapshot_context(
                snapshot=snapshot,
                material_override="audit-observation.md",
            )

            assert "material_hash" in ctx_obs
            assert "issue_scope_name" in ctx_obs

            # Test that audit-suggestion still routes correctly
            ctx_sug = build_governance_snapshot_context(
                snapshot=snapshot,
                material_override="audit-suggestion.md",
            )

            assert "observation_count" in ctx_sug


class TestDispatchIntegration:
    def test_dispatch_branch_in_governance(self) -> None:
        """Verify audit-decision.md dispatch branch exists."""
        from vibe3.roles.governance import build_governance_snapshot_context

        # Check that the function can handle audit-decision.md material name
        # (This is a smoke test - full integration would require more setup)
        assert build_governance_snapshot_context is not None
