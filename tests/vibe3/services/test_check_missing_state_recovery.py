"""Tests for check-time recovery of missing remote state labels."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients import SQLiteClient
from vibe3.models.orchestration import IssueState
from vibe3.services.check.service import CheckService


def test_verify_branch_recovers_missing_state_label_from_flow_refs(
    tmp_path: Path,
) -> None:
    """Missing remote state label is restored through resume auto inference."""
    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = "task/issue-501"
    worktree_path = tmp_path / "worktree-501"
    worktree_path.mkdir()
    (worktree_path / "plan.md").write_text("plan", encoding="utf-8")

    store.update_flow_state(
        branch,
        flow_status="active",
        plan_ref="plan.md",
        worktree_path=str(worktree_path),
    )
    store.add_issue_link(branch, 501, "task")

    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = tmp_path
    mock_git._run.return_value = branch
    mock_git.find_worktree_path_for_branch.return_value = worktree_path

    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "number": 501,
        "state": "open",
        "labels": [{"name": "roadmap/p1"}],
    }
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []
    mock_github.get_issue_body.return_value = ""
    mock_github.update_issue_body.return_value = True

    with patch(
        "vibe3.services.flow.blocked_state_io.LabelService"
    ) as mock_label_service_cls:
        mock_label_service = MagicMock()
        mock_label_service.confirm_issue_state.return_value = "advanced"
        mock_label_service_cls.return_value = mock_label_service

        service = CheckService(
            store=store, git_client=mock_git, github_client=mock_github
        )
        service._initialize_pr_cache()
        result = service.verify_branch(branch)

        assert result.is_valid is True
        mock_label_service.confirm_issue_state.assert_called_once_with(
            501,
            IssueState.IN_PROGRESS,
            actor="human:resume",
            force=True,
        )


def test_verify_branch_does_not_recover_missing_state_for_blocked_flow(
    tmp_path: Path,
) -> None:
    """Blocked flows require explicit resume; check must not auto-unblock them."""
    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = "task/issue-502"
    worktree_path = tmp_path / "worktree-502"
    worktree_path.mkdir()

    store.update_flow_state(
        branch,
        flow_status="blocked",
        worktree_path=str(worktree_path),
    )
    store.add_issue_link(branch, 502, "task")

    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = tmp_path
    mock_git._run.return_value = branch
    mock_git.find_worktree_path_for_branch.return_value = worktree_path

    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "number": 502,
        "state": "open",
        "labels": [],
    }
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []

    with patch(
        "vibe3.services.flow.blocked_state_io.LabelService"
    ) as mock_label_service_cls:
        service = CheckService(
            store=store, git_client=mock_git, github_client=mock_github
        )
        service._initialize_pr_cache()
        result = service.verify_branch(branch)

        assert result.is_valid is True
        mock_label_service_cls.assert_not_called()


def test_verify_branch_does_not_recover_missing_state_for_rfc_or_epic(
    tmp_path: Path,
) -> None:
    """RFC and epic issues may intentionally have no execution state label."""
    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = "task/issue-503"
    worktree_path = tmp_path / "worktree-503"
    worktree_path.mkdir()
    (worktree_path / "plan.md").write_text("plan", encoding="utf-8")

    store.update_flow_state(
        branch,
        flow_status="active",
        plan_ref="plan.md",
        worktree_path=str(worktree_path),
    )
    store.add_issue_link(branch, 503, "task")

    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = tmp_path
    mock_git._run.return_value = branch
    mock_git.find_worktree_path_for_branch.return_value = worktree_path

    mock_github = MagicMock()
    mock_github.view_issue.return_value = {
        "number": 503,
        "state": "open",
        "labels": [{"name": "roadmap/rfc"}, {"name": "roadmap/p1"}],
    }
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []

    with patch(
        "vibe3.services.flow.blocked_state_io.LabelService"
    ) as mock_label_service_cls:
        service = CheckService(
            store=store, git_client=mock_git, github_client=mock_github
        )
        service._initialize_pr_cache()
        result = service.verify_branch(branch)

        assert result.is_valid is True
        mock_label_service_cls.assert_not_called()


def test_verify_branch_does_not_recover_missing_state_when_issue_not_loaded(
    tmp_path: Path,
) -> None:
    """Network failures must not be treated as missing state labels."""
    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = "task/issue-504"
    worktree_path = tmp_path / "worktree-504"
    worktree_path.mkdir()

    store.update_flow_state(
        branch,
        flow_status="active",
        worktree_path=str(worktree_path),
    )
    store.add_issue_link(branch, 504, "task")

    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = tmp_path
    mock_git._run.return_value = branch
    mock_git.find_worktree_path_for_branch.return_value = worktree_path

    mock_github = MagicMock()
    mock_github.view_issue.return_value = "network_error"
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []

    with patch(
        "vibe3.services.flow.blocked_state_io.LabelService"
    ) as mock_label_service_cls:
        service = CheckService(
            store=store, git_client=mock_git, github_client=mock_github
        )
        service._initialize_pr_cache()
        result = service.verify_branch(branch)

        assert result.is_valid is False
        assert any("network/auth error" in issue for issue in result.issues)
        mock_label_service_cls.assert_not_called()


def test_verify_branch_does_not_recover_missing_state_when_labels_not_loaded(
    tmp_path: Path,
) -> None:
    """Missing or malformed label payloads must not be treated as missing state."""
    store = SQLiteClient(db_path=tmp_path / "test.db")
    branch = "task/issue-505"
    worktree_path = tmp_path / "worktree-505"
    worktree_path.mkdir()

    store.update_flow_state(
        branch,
        flow_status="active",
        worktree_path=str(worktree_path),
    )
    store.add_issue_link(branch, 505, "task")

    mock_git = MagicMock()
    mock_git.get_git_common_dir.return_value = tmp_path
    mock_git._run.return_value = branch
    mock_git.find_worktree_path_for_branch.return_value = worktree_path

    mock_github = MagicMock()
    mock_github.view_issue.return_value = {"number": 505, "state": "open"}
    mock_github.list_all_prs.return_value = []
    mock_github.list_prs_for_branch.return_value = []

    with patch(
        "vibe3.services.flow.blocked_state_io.LabelService"
    ) as mock_label_service_cls:
        service = CheckService(
            store=store, git_client=mock_git, github_client=mock_github
        )
        service._initialize_pr_cache()
        result = service.verify_branch(branch)

        assert result.is_valid is True
        mock_label_service_cls.assert_not_called()
