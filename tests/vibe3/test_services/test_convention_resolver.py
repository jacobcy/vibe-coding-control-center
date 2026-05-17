"""Tests for ConventionResolver service.

Tests verify that:
1. Resolver returns correct convention defaults
2. Convention is immutable (frozen dataclass)
3. Convention can be used for branch/label generation
"""

import pytest
from pydantic import ValidationError

from vibe3.services.convention_resolver import ConventionResolver


def test_resolver_returns_vibe_center_defaults():
    """Test resolver returns Vibe Center defaults for current repo."""
    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    assert convention.branch.task_prefix == "task/issue-"
    assert convention.manager_usernames == ["vibe-manager-agent"]


def test_resolver_returns_immutable_convention():
    """Test that resolved convention is immutable."""
    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    with pytest.raises(ValidationError):
        convention.handoff_label = "changed"


def test_convention_used_for_branch_generation():
    """Test convention can generate branch names."""
    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
    assert convention.branch.canonical_branch(123) == "task/issue-123"
    assert convention.state_label("handoff") == "state/handoff"
