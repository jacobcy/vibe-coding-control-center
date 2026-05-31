"""Tests that task resume always uses hard delete regardless of resume_kind."""

from unittest.mock import MagicMock, patch

import pytest

from tests.vibe3.services.conftest import _make_operations


@pytest.mark.parametrize(
    "resume_kind",
    ["pr_closed", "all", "blocked", "failed", "aborted"],
)
def test_reset_issue_to_ready_always_hard_deletes(resume_kind: str) -> None:
    """All resume kinds use hard delete (force_delete=True).

    Soft delete is only for vibe3 check (issue closed / flow aborted).
    Task resume means complete rebuild — old events have no value.
    """
    operations = _make_operations()

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        with patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_block_cls:
            mock_block_instance = MagicMock()
            mock_block_cls.return_value = mock_block_instance

            operations.reset_issue_to_ready(
                issue_number=123,
                resume_kind=resume_kind,
                flow=MagicMock(branch="task/issue-123"),
                repo=None,
                reason=f"Resume from {resume_kind}",
            )

            mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
                "task/issue-123",
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=False,
                force_delete=True,
            )
