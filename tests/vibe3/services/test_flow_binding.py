"""Tests for Flow binding functionality (via TaskService.link_issue)."""

from unittest.mock import MagicMock

from vibe3.models.flow import IssueLink
from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.task import TaskService


class TestFlowBinding:
    """Tests for binding tasks to flows via TaskService."""

    def test_bind_flow_success(self, mock_store) -> None:
        """Test binding a task issue to a flow via TaskService.link_issue.

        Per issue #3310 / ADR-0006: binding the task issue MUST NOT self-bind
        ``spec_ref``. The issue is recorded as a ``task`` link (queryable via
        flow_issue_links); ``spec_ref`` is set only by the canonical spec
        writer (``handoff spec`` / ``flow update --spec``).
        """
        mock_store.get_events.return_value = []
        service = TaskService(store=mock_store)
        result = service.link_issue(
            branch="test-branch",
            issue_number=123,
            role="task",
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 123
        assert result.issue_role == "task"

        mock_store.add_issue_link.assert_called_once_with("test-branch", 123, "task")
        # latest_actor is still recorded; spec_ref is NOT written here.
        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
            latest_actor="test-actor",
        )
        # Only the issue_linked event — NO spec_bound event.
        assert mock_store.add_event.call_count == 1
        event_types = [call.args[1] for call in mock_store.add_event.call_args_list]
        assert "spec_bound" not in event_types

    def test_link_issue_task_role_never_self_binds_spec_ref(self, mock_store) -> None:
        """Regression (issue #3310 acceptance): ``link_issue(role="task")``
        must never write ``spec_ref`` nor emit ``spec_bound`` — the task issue
        is bound as a link, not as the flow's spec artifact. spec_ref stays
        unset until an explicit canonical spec write occurs."""
        mock_store.get_events.return_value = []
        service = TaskService(store=mock_store)
        service.link_issue(branch="task/issue-3310", issue_number=3310, role="task")

        for call in mock_store.update_flow_state.call_args_list:
            assert "spec_ref" not in call.kwargs, (
                "link_issue(role='task') must not write spec_ref; got "
                f"{call.kwargs!r}"
            )
        event_types = [call.args[1] for call in mock_store.add_event.call_args_list]
        assert "spec_bound" not in event_types

    def test_bind_flow_already_bound(self, mock_store) -> None:
        """Binding again overwrites — link_issue is idempotent at store level."""
        mock_store.get_events.return_value = []
        service = TaskService(store=mock_store)
        result = service.link_issue(
            branch="test-branch",
            issue_number=456,
            role="task",
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 456

    def test_bind_related_role(self, mock_store) -> None:
        """Related role should remain local-only."""
        mock_store.get_events.return_value = []
        service = TaskService(store=mock_store)

        result = service.link_issue("test-branch", 219, "related")

        assert result.issue_role == "related"
        mock_store.add_issue_link.assert_called_once_with("test-branch", 219, "related")

    def test_reclassify_issue_role(self, mock_store) -> None:
        """Existing issue link can be reclassified without deleting the flow."""
        mock_store.get_events.return_value = []
        mock_store.update_issue_link_role.return_value = True
        service = TaskService(store=mock_store)

        result = service.reclassify_issue(
            "debug/vibe-server-fix",
            467,
            old_role="task",
            new_role="related",
        )

        assert result.issue_role == "related"
        mock_store.update_issue_link_role.assert_called_once_with(
            "debug/vibe-server-fix",
            467,
            "task",
            "related",
        )
        mock_store.update_flow_state.assert_called_once_with(
            "debug/vibe-server-fix",
            latest_actor="test-actor",
        )
        mock_store.add_event.assert_called_once_with(
            "debug/vibe-server-fix",
            "issue_reclassified",
            "test-actor",
            "Issue #467 reclassified: task -> related",
        )

    def test_bind_task_demotes_previous_task_flow_and_notifies_supervisor(
        self, mock_store
    ) -> None:
        mock_store.get_events.return_value = []
        mock_store.update_issue_link_role.return_value = True
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "debug/new-attempt", "flow_status": "active"},
            {"branch": "task/issue-467", "flow_status": "active"},
        ]
        mock_github = MagicMock()
        mock_github.list_prs_for_branch.return_value = [
            PRResponse(
                number=469,
                title="PR 469",
                body="",
                state=PRState.MERGED,
                head_branch="task/issue-467",
                base_branch="main",
                url="https://example.com/pr/469",
            )
        ]
        mock_github.view_issue.return_value = {
            "state": "open",
            "assignees": [{"login": "alice"}, {"login": "bob"}],
        }
        mock_label_port = MagicMock()
        mock_label_port.add_issue_label.return_value = True
        mock_label_port.get_issue_labels.return_value = ["state/claimed"]
        mock_label_port.remove_issue_label.return_value = True
        mock_label_port.ensure_label_exists.return_value = True
        config = OrchestraConfig(
            repo="owner/repo",
            supervisor_handoff=SupervisorHandoffConfig(issue_label="supervisor"),
        )

        service = TaskService(
            store=mock_store,
            github_client=mock_github,
            issue_label_port=mock_label_port,
            orchestra_config=config,
        )

        result = service.link_issue(
            branch="debug/new-attempt",
            issue_number=467,
            role="task",
            actor="codex/gpt-5.4",
        )

        assert isinstance(result, IssueLink)
        mock_store.update_issue_link_role.assert_called_once_with(
            "task/issue-467",
            467,
            "task",
            "related",
        )
        mock_github.remove_assignees.assert_called_once_with(
            467,
            ["alice", "bob"],
            repo="owner/repo",
        )
        assert mock_label_port.add_issue_label.call_args_list[0].args == (
            467,
            "supervisor",
        )
        assert mock_label_port.add_issue_label.call_args_list[1].args == (
            467,
            "state/handoff",
        )
        mock_label_port.remove_issue_label.assert_called_once_with(467, "state/claimed")
        mock_github.add_comment.assert_called_once()
        body = mock_github.add_comment.call_args.args[1]
        assert "[codex/gpt-5.4]" in body
        assert "PR #469" in body
        assert "`task/issue-467`" in body
        assert "`debug/new-attempt`" in body

    def test_bind_task_demotes_previous_task_flow_without_remote_nudge_for_noncanonical(
        self, mock_store
    ) -> None:
        mock_store.get_events.return_value = []
        mock_store.update_issue_link_role.return_value = True
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "task/issue-467", "flow_status": "active"},
            {"branch": "debug/vibe-server-fix", "flow_status": "done"},
        ]
        mock_github = MagicMock()
        mock_label_port = MagicMock()
        config = OrchestraConfig(
            repo="owner/repo",
            supervisor_handoff=SupervisorHandoffConfig(issue_label="supervisor"),
        )
        service = TaskService(
            store=mock_store,
            github_client=mock_github,
            issue_label_port=mock_label_port,
            orchestra_config=config,
        )

        service.link_issue(
            branch="task/issue-467",
            issue_number=467,
            role="task",
            actor="codex/gpt-5.4",
        )

        mock_store.update_issue_link_role.assert_called_once_with(
            "debug/vibe-server-fix",
            467,
            "task",
            "related",
        )
        mock_github.list_prs_for_branch.assert_not_called()
        mock_github.remove_assignees.assert_not_called()
        mock_github.add_comment.assert_not_called()
        mock_label_port.add_issue_label.assert_not_called()
