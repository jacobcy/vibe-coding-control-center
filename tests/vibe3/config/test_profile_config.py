"""Tests for profile-based resource resolution."""

from vibe3.adapters import get_adapter
from vibe3.config.convention_resolver import ConventionResolver
from vibe3.config.profile_config import ProfileConfig


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
    """Test ConventionResolver delegates skill lookup to adapter.

    Uses a mock adapter to avoid depending on the file-system scan in
    vibe_center.py, which fails under the isolate_database conftest because
    get_git_common_dir() is redirected to a temp directory without a skills/.
    """
    from unittest.mock import MagicMock, patch

    from vibe3.models.adapter_manifest import AdapterResource

    mock_resource = AdapterResource(
        type="skill", name="vibe-commit", path="skills/vibe-commit/SKILL.md"
    )
    mock_adapter = MagicMock()
    mock_adapter.get_resource.return_value = mock_resource

    with patch(
        "vibe3.config.profile_config.ProfileConfig._get_adapter",
        return_value=mock_adapter,
    ):
        resolver = ConventionResolver(profile="vibe-center")
        path = resolver.get_skill_path("vibe-commit")

    assert path is not None
    assert "skills/vibe-commit/SKILL.md" in path
    mock_adapter.get_resource.assert_called_once_with("skill", "vibe-commit")
