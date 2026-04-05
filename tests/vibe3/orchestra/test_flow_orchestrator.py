"""Tests for Orchestra FlowManager."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.manager.flow_manager import FlowManager
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestFlowManager:
    """Tests for FlowManager."""

    def test_get_flow_for_issue(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(
            manager.store,
            "get_flows_by_issue",
            return_value=[{"branch": "task/test", "pr_number": 123}],
        ):
            flow = manager.get_flow_for_issue(42)

        assert flow is not None
        assert flow["branch"] == "task/test"

    def test_get_flow_for_issue_returns_none(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(manager.store, "get_flows_by_issue", return_value=[]):
            flow = manager.get_flow_for_issue(42)

        assert flow is None

    def test_get_pr_for_issue_from_flow(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(
            manager,
            "get_flow_for_issue",
            return_value={"branch": "task/test", "pr_number": 789},
        ):
            pr_number = manager.get_pr_for_issue(42)

        assert pr_number == 789

    def test_get_pr_for_issue_returns_none_without_flow(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(manager, "get_flow_for_issue", return_value=None):
            with patch.object(manager.github, "get_pr_for_issue", return_value=None):
                pr_number = manager.get_pr_for_issue(42)

        assert pr_number is None

    def test_get_active_flow_count_only_counts_execution_states(self):
        config = OrchestraConfig()
        manager = FlowManager(config)

        with patch.object(
            manager.store,
            "get_all_flows",
            return_value=[
                {"branch": "task/issue-320", "flow_status": "active"},
                {"branch": "task/issue-356", "flow_status": "active"},
                {"branch": "task/issue-372", "flow_status": "active"},
                {"branch": "dev/issue-435", "flow_status": "active"},
            ],
        ):
            with patch.object(manager.store, "get_issue_links", return_value=[]):
                with patch.object(
                    manager.label_service,
                    "get_state",
                    side_effect=[
                        IssueState.READY,
                        IssueState.CLAIMED,
                        IssueState.BLOCKED,
                    ],
                ):
                    count = manager.get_active_flow_count()

        assert count == 1

    def test_create_flow_for_issue_delegates_to_git_client_create_branch_ref(self):
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=222, title="orchestra branch create")

        class _Flow:
            def model_dump(self):  # type: ignore[no-untyped-def]
                return {"branch": "task/issue-222", "flow_slug": "issue-222"}

        with patch.object(manager, "get_active_flow_count", return_value=0):
            with patch.object(manager.git, "branch_exists", return_value=False):
                with patch.object(
                    manager.git, "create_branch_ref", return_value=None
                ) as mock_create_ref:
                    with patch.object(
                        manager.flow_service,
                        "create_flow",
                        return_value=_Flow(),
                    ) as mock_create_flow:
                        with patch.object(
                            manager.task_service, "link_issue", return_value=None
                        ) as mock_link_issue:
                            flow = manager.create_flow_for_issue(issue)

        assert flow["branch"] == "task/issue-222"
        mock_create_ref.assert_called_once_with(
            "task/issue-222",
            start_ref="origin/main",
        )
        mock_create_flow.assert_called_once_with(
            slug="issue-222",
            branch="task/issue-222",
            actor=None,
            initiated_by="orchestra:manager",
        )
        mock_link_issue.assert_called_once_with(
            "task/issue-222", 222, "task", actor=None
        )

    def test_create_flow_for_issue_ignores_terminal_manual_history(self):
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=320, title="Recreate canonical scene")

        class _Flow:
            def model_dump(self):  # type: ignore[no-untyped-def]
                return {"branch": "task/issue-320", "flow_slug": "issue-320"}

        with patch.object(manager, "get_active_flow_count", return_value=0):
            with patch.object(
                manager.store,
                "get_flows_by_issue",
                return_value=[
                    {
                        "branch": "codex/fix-worktree-install-flow-done",
                        "flow_status": "done",
                    }
                ],
            ):
                with patch.object(manager.git, "branch_exists", return_value=False):
                    with patch.object(
                        manager.git, "create_branch_ref", return_value=None
                    ) as mock_create_ref:
                        with patch.object(
                            manager.flow_service,
                            "create_flow",
                            return_value=_Flow(),
                        ):
                            with patch.object(
                                manager.task_service, "link_issue", return_value=None
                            ):
                                flow = manager.create_flow_for_issue(issue)

        assert flow["branch"] == "task/issue-320"
        mock_create_ref.assert_called_once_with(
            "task/issue-320",
            start_ref="origin/main",
        )

    def test_create_flow_for_issue_rebuilds_stale_canonical_flow(self):
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=431, title="Rebuild stale flow")

        with patch.object(manager, "get_active_flow_count", return_value=0):
            with patch.object(
                manager.store,
                "get_flows_by_issue",
                return_value=[
                    {
                        "branch": "task/issue-431",
                        "flow_status": "stale",
                        "flow_slug": "issue-431",
                    }
                ],
            ):
                with patch.object(
                    manager.git,
                    "branch_exists",
                    side_effect=[True, False],
                ) as mock_branch_exists:
                    with patch.object(
                        manager.git,
                        "find_worktree_path_for_branch",
                        return_value="/tmp/issue-431",
                    ) as mock_find_worktree:
                        with patch.object(
                            manager.git,
                            "remove_worktree",
                            return_value=None,
                        ) as mock_remove_worktree:
                            with patch.object(
                                manager.git,
                                "delete_branch",
                                return_value=None,
                            ) as mock_delete_branch:
                                with patch.object(
                                    manager.git,
                                    "create_branch_ref",
                                    return_value=None,
                                ) as mock_create_ref:
                                    with patch.object(
                                        manager.flow_service,
                                        "reactivate_flow",
                                        return_value=MagicMock(
                                            model_dump=lambda: {
                                                "branch": "task/issue-431",
                                                "flow_slug": "issue-431",
                                                "flow_status": "active",
                                            }
                                        ),
                                    ) as mock_reactivate:
                                        with patch(
                                            "vibe3.manager.worktree_manager.WorktreeManager.ensure_manager_worktree",
                                            return_value=("/tmp/issue-431", True),
                                        ) as mock_ensure_worktree:
                                            with patch.object(
                                                manager.task_service,
                                                "link_issue",
                                                return_value=None,
                                            ) as mock_link:
                                                flow = manager.create_flow_for_issue(
                                                    issue
                                                )

        assert flow["branch"] == "task/issue-431"
        assert mock_branch_exists.call_count == 2
        mock_find_worktree.assert_called_once_with("task/issue-431")
        mock_remove_worktree.assert_called_once_with("/tmp/issue-431", force=True)
        mock_delete_branch.assert_called_once_with(
            "task/issue-431",
            force=True,
            skip_if_worktree=True,
        )
        mock_create_ref.assert_called_once_with(
            "task/issue-431",
            start_ref="origin/main",
        )
        mock_ensure_worktree.assert_called_once_with(431, "task/issue-431")
        mock_reactivate.assert_called_once()
        mock_link.assert_called_once_with("task/issue-431", 431, "task", actor=None)

    def test_create_flow_for_issue_deletes_new_branch_when_flow_creation_fails(self):
        """Test that newly created branch is cleaned up when flow creation fails."""
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=999, title="Failed flow creation")

        with patch.object(manager, "get_active_flow_count", return_value=0):
            with patch.object(manager.store, "get_flows_by_issue", return_value=[]):
                with patch.object(manager.git, "branch_exists", return_value=False):
                    with patch.object(
                        manager.git, "create_branch_ref", return_value=None
                    ) as mock_create_ref:
                        with patch.object(
                            manager.flow_service,
                            "create_flow",
                            side_effect=RuntimeError("Flow creation failed"),
                        ):
                            with patch.object(
                                manager.store,
                                "get_flow_state",
                                return_value=None,
                            ):
                                with patch.object(
                                    manager.git,
                                    "delete_branch",
                                    return_value=None,
                                ) as mock_delete:
                                    with pytest.raises(RuntimeError):
                                        manager.create_flow_for_issue(issue)

        mock_create_ref.assert_called_once()
        mock_delete.assert_called_once_with("task/issue-999", skip_if_worktree=True)

    def test_create_flow_for_issue_keeps_branch_when_flow_already_created_concurrently(
        self,
    ):
        """Test that branch is not deleted if flow was created concurrently."""
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=888, title="Concurrent flow creation")

        class _Flow:
            def model_dump(self):  # type: ignore[no-untyped-def]
                return {"branch": "task/issue-888", "flow_slug": "issue-888"}

        with patch.object(manager, "get_active_flow_count", return_value=0):
            with patch.object(manager.store, "get_flows_by_issue", return_value=[]):
                with patch.object(manager.git, "branch_exists", return_value=False):
                    with patch.object(
                        manager.git, "create_branch_ref", return_value=None
                    ) as mock_create_ref:
                        with patch.object(
                            manager.flow_service,
                            "create_flow",
                            side_effect=RuntimeError("Concurrent creation"),
                        ):
                            with patch.object(
                                manager.store,
                                "get_flow_state",
                                return_value={
                                    "branch": "task/issue-888",
                                    "flow_status": "active",
                                    "flow_slug": "issue-888",
                                },
                            ):
                                flow = manager.create_flow_for_issue(issue)

        mock_create_ref.assert_called_once()
        assert flow["branch"] == "task/issue-888"

    def test_create_flow_for_issue_does_not_delete_preexisting_branch_on_failure(
        self,
    ):
        """Test that pre-existing branch is not deleted on flow creation failure."""
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=777, title="Pre-existing branch failure")

        with patch.object(manager, "get_active_flow_count", return_value=0):
            with patch.object(manager.store, "get_flows_by_issue", return_value=[]):
                with patch.object(manager.git, "branch_exists", return_value=True):
                    with patch.object(
                        manager.git, "create_branch_ref", return_value=None
                    ) as mock_create_ref:
                        with patch.object(
                            manager.flow_service,
                            "create_flow",
                            side_effect=RuntimeError("Flow creation failed"),
                        ):
                            with patch.object(
                                manager.store,
                                "get_flow_state",
                                return_value=None,
                            ):
                                with patch.object(
                                    manager.git,
                                    "delete_branch",
                                    return_value=None,
                                ) as mock_delete:
                                    with pytest.raises(RuntimeError):
                                        manager.create_flow_for_issue(issue)

        mock_create_ref.assert_not_called()
        mock_delete.assert_not_called()

    def test_flow_manager_accepts_injected_clients(self):
        """Test that FlowManager can accept injected client instances."""
        from vibe3.clients.git_client import GitClient
        from vibe3.clients.github_client import GitHubClient
        from vibe3.clients.sqlite_client import SQLiteClient

        config = OrchestraConfig()
        store = SQLiteClient()
        git = GitClient()
        github = GitHubClient()

        manager = FlowManager(config, store=store, git=git, github=github)

        assert manager.store is store
        assert manager.git is git
        assert manager.github is github
        # Verify services share the same store instance
        assert manager.flow_service.store is store
        assert manager.task_service.store is store
        assert manager.issue_flow_service.store is store

    def test_flow_manager_preserves_falsey_injected_clients(self):
        """Injected collaborators should be preserved even if they are falsey."""
        config = OrchestraConfig()
        store = MagicMock()
        store.__bool__.return_value = False
        git = MagicMock()
        git.__bool__.return_value = False
        github = MagicMock()
        github.__bool__.return_value = False

        manager = FlowManager(config, store=store, git=git, github=github)

        assert manager.store is store
        assert manager.git is git
        assert manager.github is github
        assert manager.flow_service.store is store
        assert manager.flow_service.git_client is git
        assert manager.task_service.store is store
        assert manager.issue_flow_service.store is store

    def test_create_flow_for_issue_logs_cleanup_failure_but_raises_original_error(
        self,
    ):
        """Rollback cleanup failures should not mask the original flow error."""
        config = OrchestraConfig()
        manager = FlowManager(config)
        issue = make_issue(number=666, title="Cleanup failure")
        mock_log = MagicMock()

        with patch("vibe3.manager.flow_manager.logger.bind", return_value=mock_log):
            with patch.object(manager, "get_active_flow_count", return_value=0):
                with patch.object(manager.store, "get_flows_by_issue", return_value=[]):
                    with patch.object(manager.git, "branch_exists", return_value=False):
                        with patch.object(
                            manager.git, "create_branch_ref", return_value=None
                        ):
                            with patch.object(
                                manager.flow_service,
                                "create_flow",
                                side_effect=RuntimeError("Flow creation failed"),
                            ):
                                with patch.object(
                                    manager.store,
                                    "get_flow_state",
                                    return_value=None,
                                ):
                                    with patch.object(
                                        manager.git,
                                        "delete_branch",
                                        side_effect=RuntimeError("Cleanup failed"),
                                    ):
                                        with pytest.raises(
                                            RuntimeError,
                                            match=(
                                                "Failed to create flow for issue #666"
                                            ),
                                        ) as exc_info:
                                            manager.create_flow_for_issue(issue)

        assert "Flow creation failed" in str(exc_info.value)
        warning_messages = [call.args[0] for call in mock_log.warning.call_args_list]
        assert any(
            "Failed to clean up branch 'task/issue-666'" in message
            and "Cleanup failed" in message
            for message in warning_messages
        )
