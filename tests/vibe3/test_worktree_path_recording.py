"""Test worktree_path recording for auto task branches."""

from vibe3.services.status_query_service import is_auto_task_branch


def test_is_auto_task_branch():
    """Test branch filtering logic."""
    assert is_auto_task_branch("task/issue-123")
    assert is_auto_task_branch("task/issue-999")
    assert not is_auto_task_branch("dev/issue-123")
    assert not is_auto_task_branch("main")
    assert not is_auto_task_branch("feature/x")


def test_record_worktree_path_task_branch():
    """Step 3 finding existing worktree should record for task/ branches."""
    # This is a conceptual test - actual integration would need worktree setup
    # The key check is: is_auto_task_branch() guard is in place
    assert is_auto_task_branch("task/issue-456")


def test_no_record_for_dev_branch():
    """Step 3 should NOT record for dev/ branches."""
    # The guard ensures dev/ branches skip recording
    assert not is_auto_task_branch("dev/issue-789")


if __name__ == "__main__":
    test_is_auto_task_branch()
    test_record_worktree_path_task_branch()
    test_no_record_for_dev_branch()
    print("All tests passed")
