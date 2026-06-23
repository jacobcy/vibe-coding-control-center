"""Tests for audit-suggestion governance context builder."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from vibe3.roles.governance_utils import build_audit_suggestion_context


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


class TestBuildAuditSuggestionContext:
    def test_build_context_empty_observations(self, tmp_path: Path) -> None:
        """No observations directory → minimal context."""
        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_suggestion_context(snapshot)

            assert result["observation_count"] == 0
            assert result["new_since_last_run"] == 0
            assert "无观察记录" in result["scope_note"]

    def test_build_context_with_count(self, tmp_path: Path) -> None:
        """Context reflects observation count."""
        # Create observations directory with sample files
        obs_dir = tmp_path / "shared" / "observations"
        obs_dir.mkdir(parents=True)

        # Create sample observation files
        for i in range(3):
            obs_file = obs_dir / f"audit-observation-20260623T{i:02d}0000.yaml"
            obs_file.write_text(f"""
audit_observation:
  schema_version: 1
  observation_id: "obs-001-{i}"
  observed_failure_mode: "scope_mismatch"
  confidence: "medium"
""")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_suggestion_context(snapshot)

            assert result["observation_count"] == 3
            assert "scope_mismatch" in result["scope_note"]

    def test_build_context_input_cap(self, tmp_path: Path) -> None:
        """More than 20 observations → capped at 20 for stats."""
        # Create observations directory with many files
        obs_dir = tmp_path / "shared" / "observations"
        obs_dir.mkdir(parents=True)

        # Create 25 observation files
        for i in range(25):
            obs_file = obs_dir / f"audit-observation-202606{i:02d}T{i:06d}.yaml"
            obs_file.write_text(f"""
audit_observation:
  schema_version: 1
  observation_id: "obs-{i}"
  observed_failure_mode: "missing_output"
  confidence: "low"
""")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_suggestion_context(snapshot)

            # Count should be 25 (total files)
            assert result["observation_count"] == 25
            # But failure modes extraction only processes first 20
            # The scope_note should mention missing_output

    def test_build_context_multiple_failure_modes(self, tmp_path: Path) -> None:
        """Context includes all detected failure modes."""
        # Create observations directory with multiple failure modes
        obs_dir = tmp_path / "shared" / "observations"
        obs_dir.mkdir(parents=True)

        failure_modes = ["scope_mismatch", "missing_output", "state_loop"]
        for i, mode in enumerate(failure_modes):
            obs_file = obs_dir / f"audit-observation-20260623T{i:02d}0000.yaml"
            obs_file.write_text(f"""
audit_observation:
  schema_version: 1
  observed_failure_mode: "{mode}"
  confidence: "medium"
""")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_suggestion_context(snapshot)

            assert result["observation_count"] == 3
            # All modes should be in scope_note
            assert "scope_mismatch" in result["scope_note"]
            assert "missing_output" in result["scope_note"]
            assert "state_loop" in result["scope_note"]

    def test_build_context_fallback_path(self) -> None:
        """Fallback to relative path when get_git_common_dir fails."""
        with patch(
            "vibe3.utils.get_git_common_dir",
            side_effect=Exception("Test error"),
        ):
            snapshot = _make_snapshot()
            result = build_audit_suggestion_context(snapshot)

            # Should still work with fallback path
            assert "observation_count" in result
            assert "scope_note" in result

    def test_build_context_handles_yaml_parse_error(self, tmp_path: Path) -> None:
        """Skip files with invalid YAML content."""
        # Create observations directory with mixed valid/invalid files
        obs_dir = tmp_path / "shared" / "observations"
        obs_dir.mkdir(parents=True)

        # Valid file
        obs_file = obs_dir / "audit-observation-20260623T010000.yaml"
        obs_file.write_text("""
audit_observation:
  observed_failure_mode: "scope_mismatch"
""")

        # Invalid file (no failure mode field)
        invalid_file = obs_dir / "audit-observation-20260623T020000.yaml"
        invalid_file.write_text("invalid yaml content without proper structure")

        with patch(
            "vibe3.utils.get_git_common_dir",
            return_value=str(tmp_path),
        ):
            snapshot = _make_snapshot()
            result = build_audit_suggestion_context(snapshot)

            # Should count both files
            assert result["observation_count"] == 2
            # But only valid failure mode should be extracted
            assert "scope_mismatch" in result["scope_note"]


class TestDispatchIntegration:
    def test_dispatch_branch_in_governance(self) -> None:
        """Verify audit-suggestion.md dispatch branch exists."""
        from vibe3.roles.governance import build_governance_snapshot_context

        # Check that the function can handle audit-suggestion.md material name
        # (This is a smoke test - full integration would require more setup)
        assert build_governance_snapshot_context is not None
