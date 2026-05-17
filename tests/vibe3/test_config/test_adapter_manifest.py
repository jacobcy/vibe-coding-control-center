"""Tests for adapter manifest model."""

import pytest

from vibe3.config.adapter_manifest import AdapterManifest, AdapterResource


def test_adapter_manifest_simple():
    """Test basic adapter manifest creation."""
    manifest = AdapterManifest(
        name="test-adapter",
        version="1.0.0",
        description="Test adapter",
        resources=[
            AdapterResource(
                type="skill", name="test-skill", path="skills/test-skill/SKILL.md"
            )
        ],
    )
    assert manifest.name == "test-adapter"
    assert len(manifest.resources) == 1
    assert manifest.resources[0].type == "skill"


def test_adapter_manifest_multiple_resource_types():
    """Test adapter with policies and supervisor templates."""
    manifest = AdapterManifest(
        name="vibe-center",
        version="3.0.0",
        resources=[
            AdapterResource(type="policy", name="plan", path=".agent/policies/plan.md"),
            AdapterResource(type="policy", name="run", path=".agent/policies/run.md"),
            AdapterResource(
                type="supervisor", name="apply", path="supervisor/apply.md"
            ),
            AdapterResource(
                type="skill", name="vibe-commit", path="skills/vibe-commit/SKILL.md"
            ),
        ],
    )
    policies = manifest.get_resources_by_type("policy")
    assert len(policies) == 2
    assert policies[0].name == "plan"


def test_adapter_manifest_frozen():
    """Test that manifest is immutable."""
    manifest = AdapterManifest(
        name="test",
        version="1.0.0",
        resources=[AdapterResource(type="skill", name="test", path="test.md")],
    )
    with pytest.raises(Exception):
        manifest.name = "changed"
