"""Tests for orchestra server registry wiring."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import APIRouter

from vibe3.orchestra.config import OrchestraConfig
from vibe3.server import registry


class _FakeHeartbeatServer:
    def __init__(self, config, failed_gate=None):
        self.config = config
        self.failed_gate = failed_gate
        self.registered = []

    def register(self, service):
        self.registered.append(service)


def test_build_server_wires_shared_status_service_into_state_dispatchers() -> None:
    """StateLabelDispatchService 应复用共享 status_service 做预限流。"""
    config = OrchestraConfig()

    status_service = MagicMock(name="shared_status_service")
    heartbeat_holder = {}
    dispatcher_calls = []

    def fake_heartbeat(config_arg, failed_gate=None):
        heartbeat = _FakeHeartbeatServer(config_arg, failed_gate=failed_gate)
        heartbeat_holder["heartbeat"] = heartbeat
        return heartbeat

    def fake_state_dispatch_service(*args, **kwargs):
        dispatcher_calls.append(kwargs)
        return MagicMock(name=f"dispatcher-{kwargs['trigger_name']}")

    with (
        patch("vibe3.server.registry.HeartbeatServer", side_effect=fake_heartbeat),
        patch("vibe3.server.registry.GitHubClient", return_value=MagicMock()),
        patch("vibe3.server.registry.FailedGate", return_value=MagicMock()),
        patch("vibe3.server.registry.ManagerExecutor", return_value=MagicMock()),
        patch(
            "vibe3.server.registry.OrchestraStatusService",
            return_value=status_service,
        ),
        patch(
            "vibe3.server.registry.StateLabelDispatchService",
            side_effect=fake_state_dispatch_service,
        ),
        patch(
            "vibe3.server.registry.GovernanceService",
            return_value=MagicMock(name="governance"),
        ),
        patch(
            "vibe3.server.registry.SupervisorHandoffService",
            return_value=MagicMock(name="handoff"),
        ),
        patch(
            "vibe3.server.registry.AssigneeDispatchService",
            return_value=MagicMock(name="assignee"),
        ),
        patch(
            "vibe3.server.registry.PRReviewDispatchService",
            return_value=MagicMock(name="pr-review"),
        ),
        patch(
            "vibe3.server.registry.CommentReplyService",
            return_value=MagicMock(name="comment-reply"),
        ),
        patch(
            "vibe3.server.app.make_webhook_router",
            return_value=APIRouter(),
        ),
    ):
        registry._build_server_with_launch_cwd(config, launch_cwd=Path.cwd())

    assert heartbeat_holder["heartbeat"] is not None
    assert len(dispatcher_calls) == 5
    assert {call["trigger_name"] for call in dispatcher_calls} == {
        "manager",
        "plan",
        "run",
        "review",
    }
    assert all(call["status_service"] is status_service for call in dispatcher_calls)
