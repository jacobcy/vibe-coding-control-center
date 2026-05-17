"""Integration test: minimal profile has no adapter resources."""

from vibe3.services.convention_resolver import ConventionResolver


def test_minimal_profile_convention():
    """Test minimal profile returns minimal convention."""
    resolver = ConventionResolver(profile="minimal")
    convention = resolver.resolve()

    # Minimal profile should have minimal branch convention
    assert convention.branch.task_prefix == "issue-"

    # Minimal profile should have no manager usernames
    assert convention.manager_usernames == []

    # Minimal profile should have default state labels
    assert convention.state_prefix == "state/"
    assert convention.handoff_label == "handoff"
    assert convention.blocked_label == "blocked"

    # Minimal profile should have default supervisor prompt
    assert convention.supervisor_prompt == "orchestra.supervisor.apply"


def test_minimal_profile_state_labels():
    """Test minimal profile state label generation."""
    resolver = ConventionResolver(profile="minimal")
    convention = resolver.resolve()

    assert convention.state_label("handoff") == "state/handoff"
    assert convention.state_label("blocked") == "state/blocked"
