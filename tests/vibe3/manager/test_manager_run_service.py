# tests/vibe3/manager/test_manager_run_service.py
from unittest.mock import MagicMock, patch

from vibe3.execution.contracts import ExecutionLaunchResult
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestration import IssueState


def test_run_manager_reads_backend_from_env(monkeypatch):
    """VIBE3_MANAGER_BACKEND/MODEL env vars should override config resolution."""
    monkeypatch.setenv("VIBE3_MANAGER_BACKEND", "gemini")
    monkeypatch.setenv("VIBE3_MANAGER_MODEL", "gemini-3-flash-preview")

    captured_options = {}

    def fake_resolve_manager_agent_options(config, runtime_config):
        # This should NOT be called when env vars are set
        captured_options["called"] = True
        return MagicMock(backend="wrong-backend", model="wrong-model")

    with (
        patch(
            "vibe3.runtime.agent_resolver.resolve_manager_agent_options",
            side_effect=fake_resolve_manager_agent_options,
        ),
        patch("vibe3.manager.manager_run_service.OrchestraConfig") as mock_config,
        patch("vibe3.manager.manager_run_service.GitHubClient") as mock_gh,
        patch("vibe3.manager.manager_run_service.SQLiteClient"),
        patch("vibe3.manager.manager_run_service.GitClient"),
        patch("vibe3.manager.manager_run_service.CodeagentBackend") as mock_backend,
    ):

        mock_config.from_settings.return_value = MagicMock(repo=None)
        mock_gh.return_value.view_issue.return_value = {
            "number": 301,
            "title": "test",
            "labels": [],
            "state": "open",
        }
        mock_backend_instance = MagicMock()
        mock_backend.return_value = mock_backend_instance
        mock_backend_instance.start_async.return_value = MagicMock(
            tmux_session="test-session", log_path="/tmp/test.log"
        )

        from vibe3.manager.manager_run_service import run_manager_issue_mode

        try:
            run_manager_issue_mode(
                issue_number=301,
                dry_run=False,
                async_mode=True,
            )
        except Exception:
            pass

    # resolve_manager_agent_options should NOT have been called
    assert not captured_options.get(
        "called"
    ), "resolve_manager_agent_options was called even though env vars were set"


def test_run_manager_capacity_full_does_not_fail_issue() -> None:
    """Capacity rejection should not mark the issue as failed."""
    with (
        patch("vibe3.manager.manager_run_service.OrchestraConfig") as mock_config,
        patch("vibe3.manager.manager_run_service.GitHubClient") as mock_gh,
        patch("vibe3.manager.manager_run_service.SQLiteClient") as mock_store_cls,
        patch("vibe3.manager.manager_run_service.GitClient") as mock_git_cls,
        patch("vibe3.manager.manager_run_service.CodeagentBackend"),
        patch(
            "vibe3.manager.manager_run_service.ExecutionCoordinator"
        ) as mock_coord_cls,
        patch(
            "vibe3.manager.manager_run_service.build_manager_dispatch_request"
        ) as mock_prepare_request,
        patch("vibe3.manager.manager_run_service.fail_manager_issue") as mock_fail,
        patch("vibe3.manager.manager_run_service.load_session_id", return_value=None),
        patch(
            "vibe3.manager.manager_run_service.render_manager_prompt",
            return_value=MagicMock(rendered_text="prompt"),
        ),
        patch(
            "vibe3.manager.manager_run_service.format_agent_actor",
            return_value="agent:manager",
        ),
        patch("vibe3.manager.manager_run_service.typer.echo"),
    ):
        mock_config.from_settings.return_value = MagicMock(repo=None)
        mock_gh.return_value.view_issue.return_value = {
            "number": 301,
            "title": "test",
            "labels": [],
            "state": "open",
        }
        mock_git_cls.return_value.get_current_branch.return_value = "task/issue-301"
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        mock_coord = MagicMock()
        mock_coord.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False,
            reason="Capacity full for manager",
            reason_code="capacity_full",
        )
        mock_coord_cls.return_value = mock_coord
        mock_prepare_request.return_value = MagicMock()

        from vibe3.manager.manager_run_service import run_manager_issue_mode

        run_manager_issue_mode(
            issue_number=301,
            dry_run=False,
            async_mode=True,
        )

        mock_fail.assert_not_called()


def test_run_manager_sync_uses_execution_worktree_requirement() -> None:
    """Sync manager should delegate permanent worktree resolution to execution."""
    with (
        patch("vibe3.manager.manager_run_service.OrchestraConfig") as mock_config,
        patch("vibe3.manager.manager_run_service.GitHubClient") as mock_gh,
        patch("vibe3.manager.manager_run_service.SQLiteClient") as mock_store_cls,
        patch("vibe3.manager.manager_run_service.GitClient") as mock_git_cls,
        patch("vibe3.manager.manager_run_service.CodeagentBackend"),
        patch(
            "vibe3.manager.manager_run_service.ExecutionCoordinator"
        ) as mock_coord_cls,
        patch(
            "vibe3.manager.manager_run_service.render_manager_prompt",
            return_value=MagicMock(rendered_text="prompt"),
        ),
        patch(
            "vibe3.manager.manager_run_service.format_agent_actor",
            return_value="agent:manager",
        ),
        patch(
            "vibe3.manager.manager_run_service.snapshot_progress",
            side_effect=[
                {
                    "state_label": "state/ready",
                    "issue_state": "open",
                    "flow_status": "active",
                },
                {
                    "state_label": "state/in-progress",
                    "issue_state": "open",
                    "flow_status": "active",
                },
            ],
        ),
        patch("vibe3.manager.manager_run_service.typer.echo"),
    ):
        mock_config.from_settings.return_value = MagicMock(repo=None)
        mock_gh.return_value.view_issue.return_value = {
            "number": 302,
            "title": "sync manager",
            "labels": [],
            "state": "open",
        }
        mock_git_cls.return_value.get_current_branch.return_value = "main"
        mock_store_cls.return_value = MagicMock()

        captured = {}
        mock_coord = MagicMock()

        def _capture(request):
            captured["request"] = request
            return ExecutionLaunchResult(launched=True)

        mock_coord.dispatch_execution.side_effect = _capture
        mock_coord_cls.return_value = mock_coord

        from vibe3.manager.manager_run_service import run_manager_issue_mode

        run_manager_issue_mode(
            issue_number=302,
            dry_run=False,
            async_mode=False,
        )

        request = captured["request"]
        assert request.worktree_requirement == WorktreeRequirement.PERMANENT
        assert request.cwd is None


@patch("vibe3.manager.manager_run_service.AbandonFlowService")
def test_handle_closed_issue_finalizes_abandon_for_handoff(mock_abandon_service):
    """Closed HANDOFF issue should finalize PR close + flow abort.

    Uses abandon service for cleanup.
    """
    from vibe3.manager.manager_run_service import _handle_closed_issue_post_run

    store = MagicMock()
    actor = "agent:manager"
    before_snapshot = {
        "state_label": "state/handoff",
        "issue_state": "open",
        "flow_status": "active",
    }
    after_snapshot = {
        "state_label": "state/handoff",
        "issue_state": "closed",
        "flow_status": "active",
    }

    handled = _handle_closed_issue_post_run(
        store=store,
        issue_number=123,
        branch="task/issue-123",
        actor=actor,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )

    assert handled is True
    mock_abandon_service.return_value.abandon_flow.assert_called_once_with(
        issue_number=123,
        branch="task/issue-123",
        source_state=IssueState.HANDOFF,
        reason="manager closed issue without finalizing abandon flow",
        actor=actor,
        issue_already_closed=True,
        flow_already_aborted=False,
    )


@patch("vibe3.manager.manager_run_service.AbandonFlowService")
def test_handle_closed_issue_retries_cleanup_when_flow_already_aborted(
    mock_abandon_service,
):
    """Closed issue with aborted flow should still retry PR cleanup.

    Uses abandon service even when flow is already aborted.
    """
    from vibe3.manager.manager_run_service import _handle_closed_issue_post_run

    store = MagicMock()
    handled = _handle_closed_issue_post_run(
        store=store,
        issue_number=123,
        branch="task/issue-123",
        actor="agent:manager",
        before_snapshot={
            "state_label": "state/ready",
            "issue_state": "open",
            "flow_status": "active",
        },
        after_snapshot={
            "state_label": "state/ready",
            "issue_state": "closed",
            "flow_status": "aborted",
        },
    )

    assert handled is True
    mock_abandon_service.return_value.abandon_flow.assert_called_once_with(
        issue_number=123,
        branch="task/issue-123",
        source_state=IssueState.READY,
        reason="manager closed issue without finalizing abandon flow",
        actor="agent:manager",
        issue_already_closed=True,
        flow_already_aborted=True,
    )
