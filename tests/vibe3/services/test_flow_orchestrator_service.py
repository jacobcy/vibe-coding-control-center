"""Tests for FlowOrchestratorService."""

from unittest.mock import patch

from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.services.flow_orchestrator_service import FlowOrchestratorService
from vibe3.services.orchestra_status_service import OrchestraSnapshot


def test_flow_orchestrator_service_initialization() -> None:
    """FlowOrchestratorService should initialize with config."""
    config = load_orchestra_config()
    service = FlowOrchestratorService(config)

    assert service.config == config


def test_flow_orchestrator_can_snapshot() -> None:
    """FlowOrchestratorService should provide snapshot capability."""
    config = load_orchestra_config()
    service = FlowOrchestratorService(config)

    # Mock the HTTP server response via fetch_live_snapshot
    mock_snapshot = OrchestraSnapshot(
        timestamp=1234567890.0,
        server_running=True,
        active_issues=(),
        active_flows=0,
        active_worktrees=0,
    )

    with patch(
        "vibe3.services.flow_orchestrator_service.OrchestraStatusService.fetch_live_snapshot",
        return_value=mock_snapshot,
    ):
        snapshot = service.snapshot()

        assert snapshot is not None
        assert snapshot.server_running is True


def test_flow_orchestrator_snapshot_returns_none_when_unreachable() -> None:
    """FlowOrchestratorService.snapshot() returns None when server unreachable."""
    config = load_orchestra_config()
    service = FlowOrchestratorService(config)

    with patch(
        "vibe3.services.flow_orchestrator_service.OrchestraStatusService.fetch_live_snapshot",
        return_value=None,
    ):
        snapshot = service.snapshot()

        assert snapshot is None
