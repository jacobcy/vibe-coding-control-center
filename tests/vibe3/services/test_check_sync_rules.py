"""Tests for CheckService with sync rules."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import (
    LocalSyncRules,
    SQLiteClient,
    SyncRule,
    SyncRulesConfig,
)
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.check.service import CheckService
from vibe3.utils.git_helpers import get_branch_handoff_dir


@pytest.fixture(autouse=True)
def _mock_snapshot() -> Generator[None, None, None]:
    """Mock snapshot service to avoid real git operations in tests."""
    with patch("vibe3.analysis.snapshot_service.save_branch_baseline"):
        yield


class TestCheckServiceSyncRules:
    """Test CheckService._check_branch with sync rules."""

    def test_local_rule_disabled_skip(self, tmp_path: Path) -> None:
        """Disabling multi_state_label_fix skips the fix logic.

        Behavioral test: when multi_state_label_fix is disabled, the
        _check_multiple_state_labels method must not be called even if
        the issue has multiple state labels.
        """
        issue_number = 9001
        branch = f"task/issue-{issue_number}"

        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, "task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = branch
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        github_client = MagicMock(spec=GitHubClient)
        # Return issue with multiple state labels
        github_client.view_issue.return_value = {
            "state": "OPEN",
            "title": "Test issue",
            "body": "Description",
            "labels": [{"name": "state/blocked"}, {"name": "state/in-progress"}],
        }

        handoff_dir = get_branch_handoff_dir(tmp_path, branch)
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        service = CheckService(
            store=store,
            git_client=git_client,
            github_client=github_client,
        )

        # Disable multi_state_label_fix
        config = SyncRulesConfig(
            local=LocalSyncRules(multi_state_label_fix=SyncRule(enabled=False))
        )
        service._sync_rules = config

        # Mock _check_multiple_state_labels to track calls
        with patch.object(
            service,
            "_check_multiple_state_labels",
            wraps=service._check_multiple_state_labels,
        ) as mock_check:
            result = service.verify_current_flow()

            # Guard must skip the multi-state label fix
            assert mock_check.called is False

        assert result is not None
        assert result.is_valid is True

    def test_local_rule_disabled_pr(self, tmp_path: Path) -> None:
        """Disabling pr_terminal_state skips PR handling logic.

        Behavioral test: when pr_terminal_state is disabled, the
        handle_pr_terminal_state method must not be called even if
        the branch has a closed/merged PR.
        """
        issue_number = 9002
        branch = f"task/issue-{issue_number}"

        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, "task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = branch
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        github_client = MagicMock(spec=GitHubClient)
        github_client.view_issue.return_value = {
            "state": "OPEN",
            "title": "Test issue",
            "body": "Description",
            "labels": [],
        }
        # Mock a closed PR that would normally trigger terminal state
        from vibe3.models.pr import PRResponse, PRState

        closed_pr = PRResponse(
            number=123,
            title="Test PR",
            body="",
            state=PRState.CLOSED,
            head_branch=branch,
            base_branch="main",
            url="https://github.com/test/pr/123",
            draft=False,
        )
        github_client.list_prs_for_branch.return_value = [closed_pr]

        handoff_dir = get_branch_handoff_dir(tmp_path, branch)
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        service = CheckService(
            store=store,
            git_client=git_client,
            github_client=github_client,
        )

        # Disable pr_terminal_state
        config = SyncRulesConfig(
            local=LocalSyncRules(pr_terminal_state=SyncRule(enabled=False))
        )
        service._sync_rules = config

        # Mock handle_pr_terminal_state to track calls
        with patch.object(
            service._check_pr_service,
            "handle_pr_terminal_state",
            wraps=service._check_pr_service.handle_pr_terminal_state,
        ) as mock_handle:
            result = service.verify_current_flow()

            # Guard must skip PR terminal state handling
            assert mock_handle.called is False

        assert result is not None
        # Flow should remain active, not aborted
        flow = store.get_flow_state(branch)
        assert flow is not None
        assert flow["flow_status"] == "active"

    def test_default_all_enabled(self) -> None:
        """Default config produces current behavior."""
        service = CheckService()

        assert service._sync_rules.local.multi_state_label_fix.enabled is True
        assert service._sync_rules.local.pr_terminal_state.enabled is True
        assert service._sync_rules.local.closed_issue_sync.enabled is True
        assert service._sync_rules.local.stale_blocked_sync.enabled is True
        assert service._sync_rules.local.stale_ready_rebuild.enabled is True
        assert service._sync_rules.local.missing_branch_cleanup.enabled is True
        assert service._sync_rules.local.orphaned_flow_cleanup.enabled is True
        assert service._sync_rules.local.empty_ready_cleanup.enabled is True
        assert service._sync_rules.local.flow_consistency_recovery.enabled is True
        assert service._sync_rules.local.missing_state_label_recovery.enabled is True
        assert (
            service._sync_rules.local.orchestra_scanned_assignee_cleanup.enabled is True
        )
        assert service._sync_rules.local.blocked_label_sync.enabled is True

    def test_closed_issue_sync_disabled(self, tmp_path: Path) -> None:
        """Disabling closed_issue_sync skips closed issue handling.

        Behavioral test: when closed_issue_sync is disabled and the task
        issue is closed, the flow must remain "active" instead of being
        aborted.
        """
        issue_number = 9003
        branch = f"task/issue-{issue_number}"

        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, "task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = branch
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        github_client = MagicMock(spec=GitHubClient)
        # Return a CLOSED issue
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

        # Disable closed_issue_sync and other interfering rules
        config = SyncRulesConfig(
            local=LocalSyncRules(
                closed_issue_sync=SyncRule(enabled=False),
                pr_terminal_state=SyncRule(enabled=False),
                flow_consistency_recovery=SyncRule(enabled=False),
                missing_state_label_recovery=SyncRule(enabled=False),
            )
        )
        service._sync_rules = config

        result = service.verify_current_flow()

        assert result is not None
        assert result.is_valid is True
        # Flow must remain active, not aborted
        flow = store.get_flow_state(branch)
        assert flow is not None
        assert flow["flow_status"] == "active"

    def test_stale_blocked_sync_disabled(self, tmp_path: Path) -> None:
        """Disabling stale_blocked_sync skips blocked state recovery.

        Behavioral test: when stale_blocked_sync is disabled and the flow
        is "blocked" but the remote issue no longer has state/blocked,
        the flow must remain "blocked" instead of being auto-resumed.
        """
        issue_number = 9004
        branch = f"task/issue-{issue_number}"

        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(branch, flow_status="blocked")
        store.add_issue_link(branch, issue_number, "task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = branch
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        github_client = MagicMock(spec=GitHubClient)
        # Return issue with state/ready (not blocked)
        # Would normally trigger auto-resume
        github_client.view_issue.return_value = {
            "state": "OPEN",
            "title": "Test issue",
            "body": "Description",
            "labels": [{"name": "state/ready"}],
        }

        handoff_dir = get_branch_handoff_dir(tmp_path, branch)
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        service = CheckService(
            store=store,
            git_client=git_client,
            github_client=github_client,
        )

        # Disable stale_blocked_sync and other interfering rules
        config = SyncRulesConfig(
            local=LocalSyncRules(
                stale_blocked_sync=SyncRule(enabled=False),
                pr_terminal_state=SyncRule(enabled=False),
                flow_consistency_recovery=SyncRule(enabled=False),
                missing_state_label_recovery=SyncRule(enabled=False),
            )
        )
        service._sync_rules = config

        result = service.verify_current_flow()

        assert result is not None
        assert result.is_valid is True
        # Flow must remain blocked, not auto-resumed
        flow = store.get_flow_state(branch)
        assert flow is not None
        assert flow["flow_status"] == "blocked"

    def test_blocked_label_sync_disabled(self) -> None:
        """Disabling blocked_label_sync skips the sync check."""
        config = SyncRulesConfig(
            local=LocalSyncRules(blocked_label_sync=SyncRule(enabled=False))
        )

        service = CheckService()
        service._sync_rules = config

        assert service._sync_rules.local.blocked_label_sync.enabled is False

    def test_orchestra_scanned_assignee_cleanup_disabled(self) -> None:
        """Disabling orchestra_scanned_assignee_cleanup skips the cleanup."""
        config = SyncRulesConfig(
            local=LocalSyncRules(
                orchestra_scanned_assignee_cleanup=SyncRule(enabled=False)
            )
        )

        service = CheckService()
        service._sync_rules = config

        assert (
            service._sync_rules.local.orchestra_scanned_assignee_cleanup.enabled
            is False
        )
        assert service.clean_orchestra_scanned_with_assignee() == 0

    def test_pr_terminal_disabled_closed_issue_sync_no_unbound_local(
        self,
        tmp_path: Path,
    ) -> None:
        """pr_terminal_state disabled + closed_issue_sync must not UnboundLocalError.

        Regression test: when pr_terminal_state is disabled but closed_issue_sync
        is enabled (default), branch_pr must be initialized to None so the
        closed_issue_sync branch does not trigger UnboundLocalError.
        """
        issue_number = 9999
        branch = f"task/issue-{issue_number}"

        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, "task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = branch
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        github_client = MagicMock(spec=GitHubClient)
        github_client.view_issue.return_value = {
            "state": "CLOSED",
            "title": "Test issue",
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

        # Disable pr_terminal_state, keep closed_issue_sync at default (True)
        config = SyncRulesConfig(
            local=LocalSyncRules(pr_terminal_state=SyncRule(enabled=False))
        )
        service._sync_rules = config

        # This must not raise UnboundLocalError
        result = service.verify_current_flow()

        assert result is not None
        assert result.is_valid is True
        assert result.issues == []
        flow = store.get_flow_state(branch)
        assert flow is not None
        assert flow["flow_status"] == "aborted"

    def test_blocked_label_sync_syncs_local_flow_to_blocked(
        self,
        tmp_path: Path,
    ) -> None:
        """blocked_label_sync must align local flow_status to remote BLOCKED.

        Regression test: when the remote issue carries state/blocked but the
        local flow_status is not "blocked", rule_blocked_label_sync must sync
        local flow_status to "blocked" (cache-from-truth). It must NOT call
        the unblock/resume path, which would do the opposite of the rule's
        documented intent.
        """
        issue_number = 9998
        branch = f"task/issue-{issue_number}"

        store = SQLiteClient(db_path=tmp_path / "test.db")
        store.update_flow_state(branch, flow_status="active")
        store.add_issue_link(branch, issue_number, "task")

        git_client = MagicMock(spec=GitClient)
        git_client.get_current_branch.return_value = branch
        git_client.get_git_common_dir.return_value = tmp_path / ".git"

        github_client = MagicMock(spec=GitHubClient)
        github_client.view_issue.return_value = {
            "state": "OPEN",
            "title": "Test issue",
            "body": "Description",
            "labels": [{"name": "state/blocked"}],
        }

        handoff_dir = get_branch_handoff_dir(tmp_path, branch)
        handoff_dir.mkdir(parents=True, exist_ok=True)
        (handoff_dir / "current.md").touch()

        service = CheckService(
            store=store,
            git_client=git_client,
            github_client=github_client,
        )

        # Disable pr_terminal_state to avoid PR lookups; blocked_label_sync
        # remains enabled (default True).
        config = SyncRulesConfig(
            local=LocalSyncRules(pr_terminal_state=SyncRule(enabled=False))
        )
        service._sync_rules = config

        result = service.verify_current_flow()

        assert result is not None
        assert result.is_valid is True
        assert result.issues == []

        flow = store.get_flow_state(branch)
        assert flow is not None
        assert flow["flow_status"] == "blocked"

        # Remote truth must remain untouched — sync is cache-only.
        github_client.update_issue_body.assert_not_called()
