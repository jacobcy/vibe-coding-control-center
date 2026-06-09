"""Shared fixtures for command tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tests.vibe3.test_rfc_epic_utils import (
    make_orchestra_config,
    make_orchestra_snapshot,
)
from vibe3.commands.inspect import app as inspect_app
from vibe3.models.coverage import CoverageReport, LayerCoverage
from vibe3.models.flow import FlowState, FlowStatusResponse
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.handoff_status_service import HandoffStatusResult


@pytest.fixture(autouse=True)
def mock_git_client_base() -> Generator[None, None, None]:
    """Globally patch GitClient methods that require a real git repo."""
    # Use a non-protected branch name to avoid flow protection errors
    with (
        patch(
            "vibe3.clients.git_client.GitClient.get_git_common_dir",
            return_value="/tmp/.git",
        ),
        patch(
            "vibe3.clients.git_client.GitClient.get_worktree_root", return_value="/tmp"
        ),
        patch(
            "vibe3.clients.git_client.GitClient.get_current_branch",
            return_value="task/test-branch",
        ),
    ):
        yield


@pytest.fixture
def mock_pr_response() -> PRResponse:
    """Create mock PR response."""
    return PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,
    )


@pytest.fixture
def mock_coverage_all_passing() -> CoverageReport:
    """Create mock coverage report with all layers passing."""
    return CoverageReport(
        services=LayerCoverage(
            layer_name="services",
            covered_lines=850,
            total_lines=1000,
            coverage_percent=85.0,
            threshold=80,
        ),
        clients=LayerCoverage(
            layer_name="clients",
            covered_lines=420,
            total_lines=500,
            coverage_percent=84.0,
            threshold=80,
        ),
        commands=LayerCoverage(
            layer_name="commands",
            covered_lines=900,
            total_lines=1000,
            coverage_percent=90.0,
            threshold=80,
        ),
    )


@pytest.fixture
def mock_coverage_failing() -> CoverageReport:
    """Create mock coverage report with services layer failing."""
    return CoverageReport(
        services=LayerCoverage(
            layer_name="services",
            covered_lines=700,
            total_lines=1000,
            coverage_percent=70.0,
            threshold=80,
        ),
        clients=LayerCoverage(
            layer_name="clients",
            covered_lines=420,
            total_lines=500,
            coverage_percent=84.0,
            threshold=80,
        ),
        commands=LayerCoverage(
            layer_name="commands",
            covered_lines=900,
            total_lines=1000,
            coverage_percent=90.0,
            threshold=80,
        ),
    )


@pytest.fixture
def cli_runner() -> CliRunner:
    """Shared CliRunner instance for invoking CLI commands."""
    return CliRunner()


@pytest.fixture
def mock_flow_service() -> MagicMock:
    """Factory fixture that creates a configured FlowService mock.

    Returns a MagicMock with sensible defaults for FlowService methods.
    Tests should still patch at the correct module path, e.g.:
        patch("vibe3.commands.flow_manage.FlowService", return_value=mock_flow_service)
    """
    service = MagicMock()
    service.get_current_branch.return_value = "task/test-branch"
    service.store = MagicMock()
    return service


@pytest.fixture
def mock_git_client() -> MagicMock:
    """Factory fixture that creates a configured GitClient mock.

    Returns a MagicMock with sensible defaults for GitClient methods.
    Tests should still patch at the correct module path, e.g.:
        patch("vibe3.clients.git_client.GitClient", return_value=mock_git_client)
    """
    client = MagicMock()
    client.get_current_branch.return_value = "task/test-branch"
    client.get_git_common_dir.return_value = "/tmp/.git"
    client.get_worktree_root.return_value = "/tmp"
    return client


@pytest.fixture
def mock_pr_service() -> MagicMock:
    """Factory fixture that creates a configured PRService mock.

    Returns a MagicMock with sensible defaults for PRService methods.
    Tests should still patch at the correct module path, e.g.:
        patch("vibe3.commands.pr_lifecycle.PRService", return_value=mock_pr_service)
    """
    service = MagicMock()
    service.store = MagicMock()
    return service


@pytest.fixture
def mock_handoff_service() -> MagicMock:
    """Factory fixture that creates a configured HandoffService mock.

    Returns a MagicMock with sensible defaults for HandoffService methods.
    Tests should still patch at the correct module path, e.g.:
        patch(
            "vibe3.commands.handoff_write.HandoffService",
            return_value=mock_handoff_service,
        )
    """
    service = MagicMock()
    service.storage = MagicMock()
    service.storage.ensure_current_handoff.return_value = "/path/to/current.md"
    return service


@pytest.fixture
def mock_status_result() -> HandoffStatusResult:
    """Create a default HandoffStatusResult for testing."""
    return HandoffStatusResult(
        flow_slug="test-flow",
        worktree_root="/path/to/worktree",
        state=FlowState.ACTIVE,
        events=[],
        latest_verdict=None,
        live_sessions=[],
        recent_updates=[],
    )


@pytest.fixture
def mock_flow_status_response() -> FlowStatusResponse:
    """Create a default FlowStatusResponse for testing."""
    return FlowStatusResponse(
        branch="task/test-branch",
        state=FlowState.ACTIVE,
        flow_id="test-flow",
        created_at="2024-01-01T00:00:00Z",
        actors=[],
        events=[],
    )


@pytest.fixture
def inspect_app_fixture() -> Any:
    """Provide the inspect CLI app for testing."""
    return inspect_app


@pytest.fixture
def mock_pr_full() -> PRResponse:
    """Create a fully configured PR object for testing."""
    return PRResponse(
        number=123,
        title="Test PR",
        body="Test body",
        state=PRState.OPEN,
        head_branch="feature-branch",
        base_branch="main",
        url="https://github.com/org/repo/pull/123",
        draft=False,
    )


@pytest.fixture
def mock_inspect_passing() -> dict[str, Any]:
    """Mock inspect data that passes quality gate."""
    return {
        "score": {
            "score": 3.2,
            "level": "LOW",
            "block": False,
            "reason": "Low risk changes",
        }
    }


# RFC/Epic test fixtures
@pytest.fixture
def mock_orchestra_config():
    """Create a mock orchestra config for RFC/Epic tests."""
    return make_orchestra_config()


@pytest.fixture
def mock_orchestra_snapshot():
    """Create a mock orchestra snapshot for RFC/Epic tests."""
    return make_orchestra_snapshot()


@pytest.fixture
def mock_services(mock_orchestra_config, mock_orchestra_snapshot):
    """Patch all services and return mock objects.

    Returns dict with keys: config, flow_service, status_service
    """
    with (
        patch(
            "vibe3.config.orchestra_settings.load_orchestra_config"
        ) as mock_load_config,
        patch(
            "vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot"
        ) as mock_fetch_snapshot,
        patch("vibe3.services.task.status.FlowService") as mock_flow_service_cls,
        patch(
            "vibe3.services.task.status.StatusQueryService"
        ) as mock_status_service_cls,
    ):
        mock_load_config.return_value = mock_orchestra_config
        mock_fetch_snapshot.return_value = mock_orchestra_snapshot

        flow_service = MagicMock()
        flow_service.list_flows.return_value = []
        mock_flow_service_cls.return_value = flow_service

        status_service = MagicMock()
        status_service.fetch_worktree_map.return_value = {}
        status_service.fetch_orchestrated_issues.return_value = []
        mock_status_service_cls.return_value = status_service

        yield {
            "config": mock_orchestra_config,
            "flow_service": flow_service,
            "status_service": status_service,
        }
