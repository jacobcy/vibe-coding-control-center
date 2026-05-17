"""Tests for supervisor role path resolution."""

from __future__ import annotations

from vibe3.roles.supervisor import get_supervisor_prompt_path
from vibe3.services.convention_resolver import ConventionResolver


def test_supervisor_uses_profile_resolution() -> None:
    """Test supervisor prompt path uses profile resolution."""
    # With vibe-center profile
    resolver = ConventionResolver(profile="vibe-center")
    path = get_supervisor_prompt_path(resolver)
    assert path == "supervisor/apply.md"

    # With minimal profile (no supervisor)
    resolver_minimal = ConventionResolver(profile="minimal")
    path_minimal = get_supervisor_prompt_path(resolver_minimal)
    assert path_minimal is None
