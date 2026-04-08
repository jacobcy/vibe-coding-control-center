"""Tests for unified issue-flow initialization."""

import tempfile
from pathlib import Path

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.services.flow_service import FlowService


def test_ensure_flow_for_issue_branch_initializes_issue_context() -> None:
    """ensure_flow_for_branch() should initialize issue context for issue branches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Mock git client to return issue branch
        git_client = GitClient()
        git_client.get_current_branch = lambda: "task/issue-436"  # type: ignore

        service = FlowService(store=store, git_client=git_client)

        # Ensure flow for issue branch
        service.ensure_flow_for_branch("task/issue-436")

        # Verify cache was initialized
        cache = store.get_flow_context_cache("task/issue-436")
        assert cache is not None, "Cache should be initialized for issue branch"
        assert (
            cache["task_issue_number"] == 436
        ), "Issue number should be extracted from branch"


def test_ensure_flow_for_dev_branch_initializes_issue_context() -> None:
    """ensure_flow_for_branch() should initialize issue context for dev branches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        git_client = GitClient()
        git_client.get_current_branch = lambda: "dev/issue-328"  # type: ignore

        service = FlowService(store=store, git_client=git_client)

        # Ensure flow for dev branch
        service.ensure_flow_for_branch("dev/issue-328")

        # Verify cache was initialized
        cache = store.get_flow_context_cache("dev/issue-328")
        assert cache is not None, "Cache should be initialized for dev branch"
        assert (
            cache["task_issue_number"] == 328
        ), "Issue number should be extracted from dev branch"


def test_ensure_flow_for_non_issue_branch_skips_cache_init() -> None:
    """ensure_flow_for_branch() should not initialize cache for non-issue branches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        git_client = GitClient()
        git_client.get_current_branch = lambda: "feature/my-feature"  # type: ignore

        service = FlowService(store=store, git_client=git_client)

        # Ensure flow for non-issue branch
        service.ensure_flow_for_branch("feature/my-feature")

        # Verify cache was NOT initialized
        cache = store.get_flow_context_cache("feature/my-feature")
        assert cache is None, "Cache should not be initialized for non-issue branches"
