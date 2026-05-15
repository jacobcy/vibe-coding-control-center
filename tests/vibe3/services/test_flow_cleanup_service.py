from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.flow_cleanup_service import (
    FlowCleanupService,
    LiveSessionsDetectedError,
)


def test_terminate_task_sessions_raises_when_live_sessions_exist() -> None:
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )
    service.issue_flow_service.parse_issue_number.return_value = 123

    with (
        patch("vibe3.agents.backends.codeagent.CodeagentBackend") as backend_cls,
        patch("vibe3.environment.session_registry.SessionRegistryService") as registry,
    ):
        registry.return_value.get_truly_live_sessions_for_branch.return_value = [
            {"session_id": "vibe3-run-issue-123"}
        ]

        with pytest.raises(LiveSessionsDetectedError, match="live sessions found"):
            service._terminate_task_sessions("task/issue-123")
        backend_cls.assert_called_once_with()


def test_cleanup_flow_scene_aborts_when_live_sessions_exist() -> None:
    service = FlowCleanupService(
        git_client=MagicMock(),
        store=MagicMock(),
        issue_flow_service=MagicMock(),
    )
    service.issue_flow_service.is_task_branch.return_value = True

    with (
        patch.object(
            service,
            "_terminate_task_sessions",
            side_effect=LiveSessionsDetectedError("live sessions found"),
        ),
        patch.object(service, "_remove_worktree") as remove_worktree,
        patch.object(service, "_delete_local_branch") as delete_local_branch,
        patch.object(service, "_delete_remote_branch") as delete_remote_branch,
        patch.object(service, "_clear_handoff") as clear_handoff,
        patch.object(service, "_handle_flow_record") as handle_flow_record,
    ):
        with pytest.raises(LiveSessionsDetectedError, match="live sessions found"):
            service.cleanup_flow_scene("task/issue-123")

        remove_worktree.assert_not_called()
        delete_local_branch.assert_not_called()
        delete_remote_branch.assert_not_called()
        clear_handoff.assert_not_called()
        handle_flow_record.assert_not_called()
