import pytest
from pydantic import ValidationError

from vibe3.config import BranchConvention, LabelsConvention, ProfileConvention


def test_labels_convention_minimal_defaults():
    """Test LabelsConvention.minimal() has safe defaults for generic repos."""
    labels = LabelsConvention.minimal()
    assert labels.state_prefix == "state/"
    assert labels.handoff_label == "handoff"
    assert labels.blocked_label == "blocked"
    assert labels.vibe_task == "vibe-task"
    assert labels.manager_usernames == ()


def test_labels_convention_vibe_center():
    """Test LabelsConvention.vibe_center() has opinionated defaults."""
    labels = LabelsConvention.vibe_center()
    assert labels.state_prefix == "state/"
    assert labels.handoff_label == "handoff"
    assert labels.blocked_label == "blocked"
    assert labels.vibe_task == "vibe-task"
    assert labels.manager_usernames == ("vibe-manager-agent",)


def test_profile_convention_labels_property_minimal():
    """Test ProfileConvention.labels returns correct LabelsConvention.

    For minimal profile.
    """
    convention = ProfileConvention()
    assert convention.labels.state_prefix == "state/"
    assert convention.labels.handoff_label == "handoff"
    assert convention.labels.blocked_label == "blocked"
    assert convention.labels.vibe_task == "vibe-task"
    assert convention.labels.manager_usernames == ()


def test_profile_convention_labels_property_vibe_center():
    """Test ProfileConvention.labels returns correct LabelsConvention.

    For vibe-center profile.
    """
    convention = ProfileConvention.vibe_center()
    assert convention.labels.state_prefix == "state/"
    assert convention.labels.handoff_label == "handoff"
    assert convention.labels.blocked_label == "blocked"
    assert convention.labels.vibe_task == "vibe-task"
    assert convention.labels.manager_usernames == ("vibe-manager-agent",)


def test_profile_convention_custom_labels():
    """Test ProfileConvention with custom state_prefix propagates to labels."""
    custom_branch = BranchConvention(task_prefix="feature/", dev_prefix="feature/")
    convention = ProfileConvention(
        branch=custom_branch,
        state_prefix="",
        handoff_label="ready",
        blocked_label="stuck",
        manager_usernames=("my-bot",),
    )
    assert convention.labels.state_prefix == ""
    assert convention.labels.handoff_label == "ready"
    assert convention.labels.blocked_label == "stuck"
    assert convention.labels.manager_usernames == ("my-bot",)


def test_labels_property_returns_fresh_instance():
    """Test that labels property returns a fresh instance each call."""
    convention = ProfileConvention()
    labels1 = convention.labels
    labels2 = convention.labels
    # Should not be the same instance
    assert labels1 is not labels2
    # But should have equal values
    assert labels1 == labels2


def test_labels_convention_is_frozen():
    """Test that LabelsConvention is frozen (immutable)."""
    labels = LabelsConvention.minimal()
    # Attempting to modify should raise ValidationError
    with pytest.raises(ValidationError):
        labels.state_prefix = "modified/"


def test_minimal_convention_defaults():
    """Test minimal convention has safe defaults for generic repos."""
    convention = ProfileConvention()
    assert convention.branch.task_prefix == "issue-"
    assert convention.handoff_label == "handoff"
    assert convention.manager_usernames == ()


def test_vibe_center_convention():
    """Test Vibe Center opinionated defaults."""
    convention = ProfileConvention.vibe_center()
    assert convention.branch.task_prefix == "task/issue-"
    assert convention.branch.dev_prefix == "dev/issue-"
    assert convention.manager_usernames == ("vibe-manager-agent",)


def test_state_label_generation():
    """Test state label with prefix."""
    convention = ProfileConvention()
    assert convention.state_label("handoff") == "state/handoff"
    assert convention.state_label("blocked") == "state/blocked"


def test_branch_convention_integration():
    """Test BranchConvention integration."""
    convention = ProfileConvention.vibe_center()
    assert convention.branch.canonical_branch(123) == "task/issue-123"
    assert convention.branch.parse_issue_number("dev/issue-456") == 456


def test_custom_convention():
    """Test custom convention configuration."""
    custom_branch = BranchConvention(task_prefix="feature/", dev_prefix="feature/")
    convention = ProfileConvention(
        branch=custom_branch, handoff_label="ready", manager_usernames=("my-bot",)
    )
    assert convention.branch.canonical_branch(789) == "feature/789"
    assert convention.handoff_label == "ready"
    assert convention.manager_usernames == ("my-bot",)
