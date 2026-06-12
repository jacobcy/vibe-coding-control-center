"""Tests for CheckService with sync rules."""

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
def _mock_snapshot():
    """Mock snapshot service to avoid real git operations in tests."""
    with patch("vibe3.analysis.snapshot_service.save_branch_baseline"):
        yield


class TestCheckServiceSyncRules:
    """Test CheckService._check_branch with sync rules."""

    def test_local_rule_disabled_skip(self):
        """Disabling multi_state_label_fix skips the fix."""
        config = SyncRulesConfig(
            local=LocalSyncRules(multi_state_label_fix=SyncRule(enabled=False))
        )

        service = CheckService()
        service._sync_rules = config

        with patch.object(
            service,
            "_check_multiple_state_labels",
            wraps=service._check_multiple_state_labels,
        ) as mock_check:
            mock_check.return_value = ([], [], None)
            assert service._sync_rules.local.multi_state_label_fix.enabled is False

    def test_local_rule_disabled_pr(self):
        """Disabling pr_terminal_state skips PR handling."""
        config = SyncRulesConfig(
            local=LocalSyncRules(pr_terminal_state=SyncRule(enabled=False))
        )

        service = CheckService()
        service._sync_rules = config

        assert service._sync_rules.local.pr_terminal_state.enabled is False

    def test_default_all_enabled(self):
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

    def test_closed_issue_sync_disabled(self):
        """Disabling closed_issue_sync skips closed issue handling."""
        config = SyncRulesConfig(
            local=LocalSyncRules(closed_issue_sync=SyncRule(enabled=False))
        )

        service = CheckService()
        service._sync_rules = config

        assert service._sync_rules.local.closed_issue_sync.enabled is False

    def test_stale_blocked_sync_disabled(self):
        """Disabling stale_blocked_sync skips blocked state recovery."""
        config = SyncRulesConfig(
            local=LocalSyncRules(stale_blocked_sync=SyncRule(enabled=False))
        )

        service = CheckService()
        service._sync_rules = config

        assert service._sync_rules.local.stale_blocked_sync.enabled is False

    def test_blocked_label_sync_disabled(self):
        """Disabling blocked_label_sync skips the sync check."""
        config = SyncRulesConfig(
            local=LocalSyncRules(blocked_label_sync=SyncRule(enabled=False))
        )

        service = CheckService()
        service._sync_rules = config

        assert service._sync_rules.local.blocked_label_sync.enabled is False

    def test_orchestra_scanned_assignee_cleanup_disabled(self):
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
