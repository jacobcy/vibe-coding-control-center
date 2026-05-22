"""Tests for Vibe Center adapter."""

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
