"""Tests for Vibe Center adapter."""

from pathlib import Path
from unittest.mock import patch

from vibe3.adapters.vibe_center import VIBE_CENTER_ADAPTER


def test_vibe_center_adapter_exists():
    """Test Vibe Center adapter is defined."""
    assert VIBE_CENTER_ADAPTER is not None
    assert VIBE_CENTER_ADAPTER.name == "vibe-center"


def test_vibe_center_adapter_has_policies():
    """Test Vibe Center adapter declares policies."""
    policies = VIBE_CENTER_ADAPTER.get_resources_by_type("policy")
    policy_names = {p.name for p in policies}

    # Must have core policies
    assert "plan" in policy_names
    assert "run" in policy_names
    assert "review" in policy_names
    assert "common" in policy_names


def test_vibe_center_adapter_has_supervisor():
    """Test Vibe Center adapter declares supervisor template."""
    supervisor = VIBE_CENTER_ADAPTER.get_resource("supervisor", "apply")
    assert supervisor is not None
    assert supervisor.path == "supervisor/apply.md"


def test_vibe_center_adapter_skills_nonempty():
    """Test Vibe Center adapter declares some skills."""
    skills = VIBE_CENTER_ADAPTER.get_resources_by_type("skill")
    assert len(skills) > 0

    # At least vibe-commit should be present
    skill_names = {s.name for s in skills}
    assert "vibe-commit" in skill_names


def test_vibe_center_adapter_global_skills_fallback():
    """Test Vibe Center adapter falls back to ~/.vibe/skills.

    When repo skills missing.
    """
    # This test simulates external repo scenario where repo_root/skills doesn't exist
    # but global ~/.vibe/skills does exist
    from vibe3.adapters.vibe_center import _build_vibe_center_manifest

    with patch("vibe3.adapters.vibe_center.resolve_resource_root") as mock_resolve_root:
        # Simulate external repo without skills/ marker
        mock_resolve_root.return_value = Path("/tmp/external-repo")

        with patch(
            "vibe3.clients.runtime_assets.runtime_assets_root"
        ) as mock_runtime_root:
            # Mock global runtime root
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                mock_global = Path(tmpdir)
                skills_dir = mock_global / "skills"
                skills_dir.mkdir()

                # Create a mock skill
                test_skill = skills_dir / "test-skill"
                test_skill.mkdir()
                (test_skill / "SKILL.md").write_text("# Test Skill\n")

                mock_runtime_root.return_value = mock_global

                # Rebuild manifest
                manifest = _build_vibe_center_manifest()
                skills = manifest.get_resources_by_type("skill")

                # Should find test-skill from global fallback
                skill_names = {s.name for s in skills}
                assert "test-skill" in skill_names
