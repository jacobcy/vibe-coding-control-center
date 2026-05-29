"""Tests for dynamic policy path resolution in VibeConfig."""

from __future__ import annotations

from vibe3.config.settings import PlanConfig, ReviewConfig, RunConfig
from vibe3.services.convention_resolver import ConventionResolver


def test_convention_resolver_vibe_center_policy_path() -> None:
    """ConventionResolver returns standard supervisor policy paths."""
    resolver = ConventionResolver(profile="vibe-center")

    plan_path = resolver.get_policy_path("plan")
    assert plan_path == "supervisor/policies/plan.md"

    run_path = resolver.get_policy_path("run")
    assert run_path == "supervisor/policies/run.md"

    review_path = resolver.get_policy_path("review")
    assert review_path == "supervisor/policies/review.md"

    common_path = resolver.get_policy_path("common")
    assert common_path == "supervisor/policies/common.md"


def test_convention_resolver_minimal_policy_path_none() -> None:
    """ConventionResolver returns None for minimal profile (no policies)."""
    resolver = ConventionResolver(profile="minimal")

    # Minimal profile has no default policies
    plan_path = resolver.get_policy_path("plan")
    assert plan_path is None

    common_path = resolver.get_policy_path("common")
    assert common_path is None


def test_plan_config_fields_default_to_none() -> None:
    """PlanConfig policy_file and common_rules default to None."""
    config = PlanConfig()

    # Default should be None (not hardcoded path)
    assert config.policy_file is None
    assert config.common_rules is None


def test_review_config_fields_default_to_none() -> None:
    """ReviewConfig policy_file and common_rules default to None."""
    config = ReviewConfig()

    assert config.policy_file is None
    assert config.common_rules is None


def test_run_config_fields_default_to_none() -> None:
    """RunConfig policy_file and common_rules default to None."""
    config = RunConfig()

    assert config.policy_file is None
    assert config.common_rules is None
