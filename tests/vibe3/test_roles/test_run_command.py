"""Tests for run_command skill resolution."""

from vibe3.roles.run_command import resolve_skill_path
from vibe3.services.convention_resolver import ConventionResolver


def test_skill_path_uses_profile():
    """Test skill lookup uses profile resolution."""
    resolver = ConventionResolver(profile="vibe-center")
    path = resolve_skill_path("vibe-commit", resolver)
    assert path is not None
    assert "skills/vibe-commit/SKILL.md" in path

    resolver_minimal = ConventionResolver(profile="minimal")
    path_minimal = resolve_skill_path("vibe-commit", resolver_minimal)
    assert path_minimal is None


def test_skill_path_returns_none_for_missing():
    """Test that missing skills return None."""
    resolver = ConventionResolver(profile="minimal")
    path = resolve_skill_path("nonexistent-skill", resolver)
    assert path is None


def test_skill_path_without_resolver_uses_default():
    """Test that omitting resolver uses default from_repo().

    In vibe-center repo (detected via git remote), should find vibe-commit.
    In external repos, should return None (minimal profile).
    """
    import os

    # Force vibe-center profile to make test deterministic
    original_profile = os.environ.get("VIBE_PROFILE")
    try:
        os.environ["VIBE_PROFILE"] = "vibe-center"
        path = resolve_skill_path("vibe-commit")
        assert path is not None
        assert "skills/vibe-commit/SKILL.md" in path
    finally:
        if original_profile is None:
            os.environ.pop("VIBE_PROFILE", None)
        else:
            os.environ["VIBE_PROFILE"] = original_profile
