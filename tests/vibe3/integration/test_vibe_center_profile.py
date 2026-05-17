"""Integration test: vibe-center profile loads all resources."""

from pathlib import Path

from vibe3.services.convention_resolver import ConventionResolver


def test_vibe_center_profile_has_policies():
    """Test vibe-center profile policy files exist."""
    # Policy paths are defined in VibeConfig defaults
    # For vibe-center, these should be accessible in the repo
    policy_files = [
        ".agent/policies/plan.md",
        ".agent/policies/run.md",
        ".agent/policies/review.md",
        ".agent/policies/common.md",
    ]

    for policy_file in policy_files:
        path = Path(policy_file)
        # Check if file exists (relative to project root)
        assert path.exists(), f"Policy file {policy_file} should exist"


def test_vibe_center_profile_has_supervisor():
    """Test vibe-center profile supervisor templates exist."""
    supervisor_templates = [
        "supervisor/apply.md",
    ]

    for template in supervisor_templates:
        path = Path(template)
        # Check if file exists (relative to project root)
        assert path.exists(), f"Supervisor template {template} should exist"


def test_vibe_center_profile_has_skills():
    """Test vibe-center profile skill files exist."""
    # Check for at least vibe-commit skill
    skill_path = Path("skills/vibe-commit/SKILL.md")
    assert skill_path.exists(), "vibe-commit skill should exist"


def test_vibe_center_profile_branch_convention():
    """Test vibe-center profile has opinionated conventions."""
    resolver = ConventionResolver(profile="vibe-center")
    convention = resolver.resolve()

    # Verify vibe-center specific conventions
    assert convention.branch.task_prefix == "task/issue-"
    assert "vibe-manager-agent" in convention.manager_usernames
    assert convention.state_prefix == "state/"
    assert convention.handoff_label == "handoff"
    assert convention.blocked_label == "blocked"
