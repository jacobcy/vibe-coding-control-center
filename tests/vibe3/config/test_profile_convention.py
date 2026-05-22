from vibe3.config.profile_convention import ProfileConvention
from vibe3.models.branch_convention import BranchConvention


def test_minimal_convention_defaults():
    """Test minimal convention has safe defaults for generic repos."""
    convention = ProfileConvention()
    assert convention.branch.task_prefix == "issue-"
    assert convention.handoff_label == "handoff"
    assert convention.manager_usernames == []


def test_vibe_center_convention():
    """Test Vibe Center opinionated defaults."""
    convention = ProfileConvention.vibe_center()
    assert convention.branch.task_prefix == "task/issue-"
    assert convention.branch.dev_prefix == "dev/issue-"
    assert convention.manager_usernames == ["vibe-manager-agent"]


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
        branch=custom_branch, handoff_label="ready", manager_usernames=["my-bot"]
    )
    assert convention.branch.canonical_branch(789) == "feature/789"
    assert convention.handoff_label == "ready"
    assert convention.manager_usernames == ["my-bot"]
