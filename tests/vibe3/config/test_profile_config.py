"""Tests for profile-based resource resolution."""

from vibe3.adapters import get_adapter
from vibe3.config import ProfileConfig
from vibe3.services.convention_resolver import ConventionResolver


def test_profile_config_vibe_center_loads_adapter() -> None:
    """Test vibe-center profile loads vibe-center adapter."""
    config = ProfileConfig(profile="vibe-center", adapter_resolver=get_adapter)
    policy_path = config.get_policy_path("plan")
    assert policy_path == "supervisor/policies/plan.md"


def test_profile_config_minimal_returns_none() -> None:
    """Test minimal profile has no adapter resources."""
    config = ProfileConfig(profile="minimal", adapter_resolver=get_adapter)
    policy_path = config.get_policy_path("plan")
    # Minimal profile has no policies
    assert policy_path is None


def test_convention_resolver_gets_policy_path() -> None:
    """Test ConventionResolver can resolve policy paths."""
    resolver = ConventionResolver(profile="vibe-center")
    path = resolver.get_policy_path("common")
    assert path == "supervisor/policies/common.md"


def test_convention_resolver_gets_skill_path() -> None:
    """Test ConventionResolver can resolve skill paths."""
    resolver = ConventionResolver(profile="vibe-center")
    # vibe-commit should exist in vibe-center
    path = resolver.get_skill_path("vibe-commit")
    assert path is not None
    assert "skills/vibe-commit/SKILL.md" in path
