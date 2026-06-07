"""Tests for CheckService.verify_branch single-branch verification."""

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients import SQLiteClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.check_service import CheckService


def test_verify_branch_returns_check_result(tmp_path: Path) -> None:
    """verify_branch should return CheckResult for a single branch."""
    # Create temp store
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    temp_store = SQLiteClient(db_path=db_path)

    # Mock GitHub client to avoid gh CLI calls in CI
    mock_github = MagicMock()
    mock_github.list_all_prs.return_value = []

    service = CheckService(store=temp_store, git_client=None, github_client=mock_github)

    # Setup: create a minimal flow record
    branch = "dev/test-123"

    timestamp = datetime.now().isoformat()
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES (?, ?, 'active', ?)
            """,
            (branch, "test_flow", timestamp),
        )

    result = service.verify_branch(branch)

    assert result.branch == branch
    assert isinstance(result.is_valid, bool)
    assert isinstance(result.issues, list)


def test_verify_branch_returns_invalid_for_missing_flow(tmp_path: Path) -> None:
    """verify_branch should return invalid result for unknown branch."""
    # Create temp store
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    temp_store = SQLiteClient(db_path=db_path)

    # Mock GitHub client to avoid gh CLI calls in CI
    mock_github = MagicMock()
    mock_github.list_all_prs.return_value = []

    service = CheckService(store=temp_store, github_client=mock_github)

    result = service.verify_branch("nonexistent-branch")

    assert result.is_valid is False
    assert "No flow record" in result.issues[0]


def test_verify_branch_rejects_protected_branch(tmp_path: Path) -> None:
    """verify_branch should reject protected branches (main, master, develop)."""
    # Create temp store
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    temp_store = SQLiteClient(db_path=db_path)

    service = CheckService(store=temp_store)

    # Test main branch
    result = service.verify_branch("main")
    assert result.is_valid is False
    assert "protected" in result.issues[0].lower()
    assert "main" in result.issues[0]

    # Test master branch
    result = service.verify_branch("master")
    assert result.is_valid is False
    assert "protected" in result.issues[0].lower()

    # Test develop branch
    result = service.verify_branch("develop")
    assert result.is_valid is False
    assert "protected" in result.issues[0].lower()

    # Test origin/main (remote branch)
    result = service.verify_branch("origin/main")
    assert result.is_valid is False
    assert "remote" in result.issues[0].lower()
    assert "origin/main" in result.issues[0]

    # Test origin/develop (remote branch)
    result = service.verify_branch("origin/develop")
    assert result.is_valid is False
    assert "remote" in result.issues[0].lower()


def test_verify_branch_handles_merged_pr(tmp_path: Path) -> None:
    """verify_branch should mark flow as done when PR is merged."""
    # Create temp store
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    temp_store = SQLiteClient(db_path=db_path)

    # Mock git client
    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = str(tmp_path / ".git")

    # Mock GitHub client
    mock_github = MagicMock()

    service = CheckService(
        store=temp_store,
        git_client=mock_git,
        github_client=mock_github,
    )

    # Setup: create a flow record
    branch = "dev/test-merged-pr"

    timestamp = datetime.now().isoformat()
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES (?, ?, 'active', ?)
            """,
            (branch, "test_flow", timestamp),
        )

    # Setup: mock merged PR
    merged_pr = PRResponse(
        number=42,
        title="Test PR",
        state=PRState.MERGED,
        head_branch=branch,
        base_branch="main",
        url="https://github.com/test/test/pull/42",
        merged_at="2024-01-01T00:00:00Z",
    )
    service._branch_to_pr = {branch: merged_pr}

    # Mock flow_status_service.mark_flow_done to avoid side effects
    with patch.object(service._flow_status_service, "mark_flow_done") as mock_mark_done:
        mock_mark_done.return_value = {"issue_to_close": None}
        result = service.verify_branch(branch)

        # Should call mark_flow_done
        mock_mark_done.assert_called_once()
        assert result.is_valid is True


def test_verify_branch_handles_closed_pr(tmp_path: Path) -> None:
    """verify_branch should mark flow as aborted when PR is closed without merge."""
    # Create temp store
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    temp_store = SQLiteClient(db_path=db_path)

    # Mock git client
    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = str(tmp_path / ".git")

    # Mock GitHub client
    mock_github = MagicMock()

    service = CheckService(
        store=temp_store,
        git_client=mock_git,
        github_client=mock_github,
    )

    # Setup: create a flow record
    branch = "dev/test-closed-pr"

    timestamp = datetime.now().isoformat()
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES (?, ?, 'active', ?)
            """,
            (branch, "test_flow", timestamp),
        )

    # Setup: mock closed PR (not merged)
    closed_pr = PRResponse(
        number=43,
        title="Test PR",
        state=PRState.CLOSED,
        head_branch=branch,
        base_branch="main",
        url="https://github.com/test/test/pull/43",
        merged_at=None,
    )
    service._branch_to_pr = {branch: closed_pr}

    # Mock _reset_issue_after_pr_closed to avoid side effects
    with patch.object(
        service._check_pr_service, "_reset_issue_after_pr_closed"
    ) as mock_reset:
        mock_reset.return_value = (None, [])
        result = service.verify_branch(branch)

        # Should call _reset_issue_after_pr_closed
        mock_reset.assert_called_once()
        assert result.is_valid is True


def test_verify_branch_handles_missing_worktree_and_ref_files(tmp_path: Path) -> None:
    """verify_branch should report issues for missing worktree with ref files."""
    # Create temp store
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    temp_store = SQLiteClient(db_path=db_path)

    # Mock git client
    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = str(tmp_path / ".git")
    mock_git.find_worktree_path_for_branch.return_value = None  # No worktree

    # Mock GitHub client
    mock_github = MagicMock()
    mock_github.list_prs_for_branch.return_value = []  # No PR

    service = CheckService(
        store=temp_store,
        git_client=mock_git,
        github_client=mock_github,
    )

    # Setup: create a flow record with ref files
    branch = "dev/test-missing-worktree"
    mock_git._run.return_value = f"  {branch}\n"  # Branch exists locally

    timestamp = datetime.now().isoformat()
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO flow_state (
                branch, flow_slug, flow_status,
                plan_ref, report_ref, updated_at
            )
            VALUES (?, ?, 'active', ?, ?, ?)
            """,
            (branch, "test_flow", "plans/test.md", "reports/test.md", timestamp),
        )

    result = service.verify_branch(branch)

    # Should report issues about missing worktree and ref files
    assert result.is_valid is False
    assert len(result.issues) > 0
    # Missing worktree/ref scenes must route operators to explicit rebuild.
    assert any("vibe3 flow rebuild" in issue for issue in result.issues)
    assert all("task resume" not in issue for issue in result.issues)


def test_verify_branch_no_longer_reports_runtime_ownership_warnings(
    tmp_path: Path,
) -> None:
    """verify_branch should not report removed ownership diagnostics.

    After runtime simplification, verify no legacy owner-session diagnostics.
    """
    # Create temp store
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    temp_store = SQLiteClient(db_path=db_path)

    # Mock git client
    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = str(tmp_path / ".git")
    mock_git.find_worktree_path_for_branch.return_value = None  # No worktree

    # Mock GitHub client
    mock_github = MagicMock()
    mock_github.list_all_prs.return_value = []

    service = CheckService(
        store=temp_store,
        git_client=mock_git,
        github_client=mock_github,
    )

    # Setup: create a flow record
    branch = "task/issue-321"
    mock_git._run.return_value = f"  {branch}\n"  # Branch exists locally

    timestamp = datetime.now().isoformat()
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES (?, ?, 'active', ?)
            """,
            (branch, "test_flow", timestamp),
        )

    result = service.verify_branch(branch)

    # Should NOT report any removed owner-session warnings
    assert all("owner session" not in issue for issue in result.issues)
    assert all("owner session" not in warning for warning in result.warnings)


def test_verify_branch_closed_issue_returns_invalid(tmp_path: Path) -> None:
    """Closed issue without open PR must return is_valid=False."""
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient

    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = "task/issue-1629"
    store.update_flow_state(branch, flow_status="active")
    store.add_issue_link(branch, 1629, "task")

    mock_git = MagicMock(spec=GitClient)
    mock_git.find_worktree_path_for_branch.return_value = None
    mock_git.get_git_common_dir.return_value = tmp_path

    mock_github = MagicMock(spec=GitHubClient)
    mock_github.view_issue.return_value = {
        "number": 1629,
        "state": "CLOSED",
        "labels": [],
    }
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []
    mock_github.close_issue_if_open.return_value = "already_closed"

    service = CheckService(store=store, git_client=mock_git, github_client=mock_github)
    service._initialize_pr_cache()

    result = service.verify_branch(branch)

    # Closed issue = NOT valid for dispatch
    assert result.is_valid is False


def test_verify_branch_unblocks_stale_blocked_flow(tmp_path: Path) -> None:
    """When flow is locally blocked but remote state/blocked was removed, unblock it."""
    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = "task/issue-500"

    # Set up blocked flow with stale blocked markers
    store.update_flow_state(
        branch,
        flow_status="blocked",
        blocked_by_issue=100,
        blocked_reason="waiting for PR #100",
    )
    store.add_issue_link(branch, 500, "task")

    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = tmp_path
    # Non-empty return means branch exists locally
    mock_git._run.return_value = branch

    mock_github = MagicMock()
    # Issue 500 has state/ready — remote state/blocked was removed
    mock_github.view_issue.return_value = {
        "number": 500,
        "state": "open",
        "labels": [{"name": "state/ready"}],
    }
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []

    service = CheckService(store=store, git_client=mock_git, github_client=mock_github)
    service._initialize_pr_cache()
    result = service.verify_branch(branch)

    assert result.is_valid is True

    # DB blocked state must be cleared
    flow = store.get_flow_state(branch)
    assert flow is not None
    assert flow.get("flow_status") == "active"
    assert flow.get("blocked_by_issue") is None
    assert flow.get("blocked_reason") is None
