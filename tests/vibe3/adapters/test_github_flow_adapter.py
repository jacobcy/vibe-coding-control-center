"""Tests for GitHub Flow adapter."""

from pathlib import Path

from vibe3.adapters import get_adapter


def test_github_flow_adapter_exists():
    """Test GitHub Flow adapter is defined."""
    adapter = get_adapter("github-flow")
    assert adapter is not None
    assert adapter.name == "github-flow"


def test_github_flow_adapter_registration():
    """Test GitHub Flow adapter is registered and accessible via get_adapter."""
    adapter = get_adapter("github-flow")
    assert adapter is not None
    assert adapter.name == "github-flow"


def test_github_flow_adapter_scans_global_skills():
    """Test GitHub Flow adapter scans skills from ~/.vibe/skills."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_root = Path(tmpdir)
        skills_dir = mock_root / "skills"
        skills_dir.mkdir()

        # Create mock skill
        vibe_commit_skill = skills_dir / "vibe-commit"
        vibe_commit_skill.mkdir()
        (vibe_commit_skill / "SKILL.md").write_text("# vibe-commit skill\n")

        # Build manifest with mocked global_skills
        from vibe3.adapters.github_flow import _build_github_flow_manifest

        manifest = _build_github_flow_manifest(global_skills=skills_dir)
        skills = manifest.get_resources_by_type("skill")

        assert len(skills) > 0

        # Should include vibe-commit
        skill_names = {s.name for s in skills}
        assert "vibe-commit" in skill_names


def test_github_flow_adapter_skill_paths():
    """Test GitHub Flow adapter skill paths are relative to ~/.vibe."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        mock_root = Path(tmpdir)
        skills_dir = mock_root / "skills"
        skills_dir.mkdir()

        # Create mock skill
        vibe_commit_skill = skills_dir / "vibe-commit"
        vibe_commit_skill.mkdir()
        (vibe_commit_skill / "SKILL.md").write_text("# vibe-commit skill\n")

        # Build manifest with mocked global_skills
        from vibe3.adapters.github_flow import _build_github_flow_manifest

        manifest = _build_github_flow_manifest(global_skills=skills_dir)
        skills = manifest.get_resources_by_type("skill")
        vibe_commit = next((s for s in skills if s.name == "vibe-commit"), None)
        assert vibe_commit is not None
        # Path should be relative to ~/.vibe
        assert "skills/vibe-commit/SKILL.md" in vibe_commit.path


def test_github_flow_adapter_with_mocked_runtime_root():
    """Test GitHub Flow adapter when ~/.vibe/skills doesn't exist."""
    # Build manifest with None global_skills
    from vibe3.adapters.github_flow import _build_github_flow_manifest

    manifest = _build_github_flow_manifest(global_skills=None)
    skills = manifest.get_resources_by_type("skill")

    # Should have no skills if global_skills is None
    assert len(skills) == 0
