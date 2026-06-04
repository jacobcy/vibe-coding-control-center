"""Tests for GitHub Flow adapter."""

from pathlib import Path
from unittest.mock import patch

from vibe3.adapters import get_adapter
from vibe3.adapters.github_flow import GITHUB_FLOW_ADAPTER


def test_github_flow_adapter_exists():
    """Test GitHub Flow adapter is defined."""
    assert GITHUB_FLOW_ADAPTER is not None
    assert GITHUB_FLOW_ADAPTER.name == "github-flow"


def test_github_flow_adapter_registration():
    """Test GitHub Flow adapter is registered and accessible via get_adapter."""
    adapter = get_adapter("github-flow")
    assert adapter is not None
    assert adapter.name == "github-flow"


def test_github_flow_adapter_scans_global_skills():
    """Test GitHub Flow adapter scans skills from ~/.vibe/skills."""
    skills = GITHUB_FLOW_ADAPTER.get_resources_by_type("skill")
    assert len(skills) > 0

    # Should include vibe-commit if global runtime is synced
    skill_names = {s.name for s in skills}
    assert "vibe-commit" in skill_names


def test_github_flow_adapter_skill_paths():
    """Test GitHub Flow adapter skill paths are relative to ~/.vibe."""
    skills = GITHUB_FLOW_ADAPTER.get_resources_by_type("skill")
    vibe_commit = next((s for s in skills if s.name == "vibe-commit"), None)
    assert vibe_commit is not None
    # Path should be relative to ~/.vibe
    assert "skills/vibe-commit/SKILL.md" in vibe_commit.path


def test_github_flow_adapter_with_mocked_runtime_root():
    """Test GitHub Flow adapter when ~/.vibe/skills doesn't exist."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_root = Path(tmpdir)

        with patch(
            "vibe3.adapters.github_flow.runtime_assets_root", return_value=mock_root
        ):
            # Rebuild manifest with mocked root
            from vibe3.adapters.github_flow import _build_github_flow_manifest

            manifest = _build_github_flow_manifest()
            skills = manifest.get_resources_by_type("skill")

            # Should have no skills if mock root has no skills/ directory
            assert len(skills) == 0
