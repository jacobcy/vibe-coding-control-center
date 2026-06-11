"""Tests for check handling of closed task issues with branch PR status."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.check.service import CheckService
from vibe3.utils.git_helpers import get_branch_handoff_dir


@pytest.fixture(autouse=True)
def _mock_snapshot():
    """Mock snapshot service to avoid real git operations in tests."""
    with patch("vibe3.analysis.snapshot_service.save_branch_baseline"):
        yield


def _make_service(
    tmp_path: Path,
    *,
    issue_number: int,
    pr: PRResponse | None,
) -> tuple[SQLiteClient, CheckService, str]:
    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = f"task/issue-{issue_number}"
    store.update_flow_state(
        branch,
        flow_slug=f"issue_{issue_number}",
        flow_status="active",
    )
    store.add_issue_link(branch, issue_number, "task")

    git_client = MagicMock(spec=GitClient)
    git_client.get_current_branch.return_value = branch
    git_client.get_git_common_dir.return_value = tmp_path / ".git"

    github_client = MagicMock(spec=GitHubClient)
    github_client.list_prs_for_branch.return_value = [pr] if pr else []
    github_client.list_all_prs.return_value = [pr] if pr else []
    github_client.view_issue.return_value = {
        "state": "CLOSED",
        "title": "Closed issue",
        "body": "Description",
        "labels": [],
    }

    handoff_dir = get_branch_handoff_dir(tmp_path, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    (handoff_dir / "current.md").touch()

    service = CheckService(
        store=store,
        git_client=git_client,
        github_client=github_client,
    )
    return store, service, branch


def test_check_marks_flow_done_when_merged_with_closed_issue(tmp_path: Path) -> None:
    """Merged PR wins over closed issue and marks the flow done."""
    merged_pr = PRResponse(
        number=42,
        title="Fix PR merged flow misclassification",
        state=PRState.MERGED,
        head_branch="task/issue-2284",
        base_branch="main",
        url="https://github.com/test/pr/42",
        merged_at="2026-06-07T00:00:00Z",
        draft=False,
        is_ready=True,
        ci_passed=True,
    )
    store, service, branch = _make_service(tmp_path, issue_number=2284, pr=merged_pr)

    service.verify_current_flow()

    flow = store.get_flow_state(branch)
    assert flow is not None
    assert flow["flow_status"] == "done"


def test_check_closed_issue_without_pr_aborts_flow(tmp_path: Path) -> None:
    """Closed issue plus no PR is a terminal stale flow."""
    store, service, branch = _make_service(tmp_path, issue_number=999, pr=None)

    result = service.verify_current_flow()

    assert result is not None
    assert result.is_valid is True
    assert result.issues == []
    flow = store.get_flow_state(branch)
    assert flow is not None
    assert flow["flow_status"] == "aborted"


def test_check_closed_issue_with_open_pr_skips_flow(tmp_path: Path) -> None:
    """Closed issue with an open PR should not abort the active flow."""
    open_pr = PRResponse(
        number=77,
        title="Open PR for closed issue",
        state=PRState.OPEN,
        head_branch="task/issue-1000",
        base_branch="main",
        url="https://github.com/test/pr/77",
        draft=False,
    )
    store, service, branch = _make_service(tmp_path, issue_number=1000, pr=open_pr)

    result = service.verify_current_flow()

    assert result is not None
    assert result.is_valid is True
    flow = store.get_flow_state(branch)
    assert flow is not None
    assert flow["flow_status"] == "active"


def test_check_closed_issue_with_closed_pr_aborts_and_cleans_flow(
    tmp_path: Path,
) -> None:
    """Closed PR for a closed issue follows the existing abort cleanup path."""
    closed_pr = PRResponse(
        number=78,
        title="Closed PR for closed issue",
        state=PRState.CLOSED,
        head_branch="task/issue-1001",
        base_branch="main",
        url="https://github.com/test/pr/78",
        draft=False,
    )
    store, service, branch = _make_service(tmp_path, issue_number=1001, pr=closed_pr)

    result = service.verify_current_flow()

    assert result is not None
    assert result.is_valid is True
    assert store.get_flow_state(branch) is None
