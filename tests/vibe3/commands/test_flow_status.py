"""Tests for flow status commands."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.data_source import DataSource
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


# ==============================================================================
# Test: flow show --format json
# ==============================================================================


def test_flow_show_format_json() -> None:
    """Test flow show with --format json works correctly."""
    branch = "dev/issue-123"
    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status="active",
        task_issue_number=123,
        timeline=[],
        data_source=DataSource.LOCAL_SQLITE,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch("vibe3.services.FlowStatusResolver") as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                mock_service = MagicMock()
                mock_service_class.return_value = mock_service
                mock_service.store.get_events.return_value = []

                mock_resolver = MagicMock()
                mock_resolver.resolve.return_value = flow_status
                mock_resolver_class.return_value = mock_resolver

                mock_projection = MagicMock()
                mock_projection.get_issue_titles.return_value = ({}, None)
                mock_projection_class.return_value = mock_projection

                result = runner.invoke(app, ["flow", "show", "--format", "json"])

                assert result.exit_code == 0
                output = json.loads(result.output)
                assert "state" in output
                assert "events" in output


def test_flow_show_format_yaml() -> None:
    """Test flow show with --format yaml works correctly."""
    branch = "dev/issue-123"
    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status="active",
        task_issue_number=123,
        timeline=[],
        data_source=DataSource.LOCAL_SQLITE,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch("vibe3.services.FlowStatusResolver") as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                mock_service = MagicMock()
                mock_service_class.return_value = mock_service
                mock_service.store.get_events.return_value = []

                mock_resolver = MagicMock()
                mock_resolver.resolve.return_value = flow_status
                mock_resolver_class.return_value = mock_resolver

                mock_projection = MagicMock()
                mock_projection.get_issue_titles.return_value = ({}, None)
                mock_projection_class.return_value = mock_projection

                result = runner.invoke(app, ["flow", "show", "--format", "yaml"])

                assert result.exit_code == 0
                assert "state:" in result.output
                assert "events:" in result.output


# ==============================================================================
# Test: flow status --format json
# ==============================================================================


def test_flow_status_format_json() -> None:
    """Test flow status with --format json works correctly."""
    mock_flows = [
        FlowStatusResponse(
            branch="dev/issue-123",
            flow_slug="dev-issue-123",
            flow_status="active",
            task_issue_number=123,
            timeline=[],
            data_source=DataSource.LOCAL_SQLITE,
        ),
    ]

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowProjectionService"
        ) as mock_projection_class:
            with patch(
                "vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot",
                return_value=None,
            ):
                mock_service = MagicMock()
                mock_service.list_flows.return_value = mock_flows
                mock_service_class.return_value = mock_service

                mock_projection = MagicMock()
                mock_projection.get_issue_titles.return_value = ({}, None)
                mock_projection_class.return_value = mock_projection

                result = runner.invoke(app, ["flow", "status", "--format", "json"])

                assert result.exit_code == 0
                output = json.loads(result.output)
                assert isinstance(output, list)
                assert len(output) == 1


def test_flow_status_format_yaml() -> None:
    """Test flow status with --format yaml works correctly."""
    mock_flows = [
        FlowStatusResponse(
            branch="dev/issue-123",
            flow_slug="dev-issue-123",
            flow_status="active",
            task_issue_number=123,
            timeline=[],
            data_source=DataSource.LOCAL_SQLITE,
        ),
    ]

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowProjectionService"
        ) as mock_projection_class:
            with patch(
                "vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot",
                return_value=None,
            ):
                mock_service = MagicMock()
                mock_service.list_flows.return_value = mock_flows
                mock_service_class.return_value = mock_service

                mock_projection = MagicMock()
                mock_projection.get_issue_titles.return_value = ({}, None)
                mock_projection_class.return_value = mock_projection

                result = runner.invoke(app, ["flow", "status", "--format", "yaml"])

                assert result.exit_code == 0
                assert "branch: dev/issue-123" in result.output


# ==============================================================================
# Test: Ensure --json is NOT accepted (removed)
# ==============================================================================


def test_flow_show_rejects_json_flag() -> None:
    """Test that flow show rejects the deprecated --json flag."""
    result = runner.invoke(app, ["flow", "show", "--json"])
    # Should fail with error (unknown option)
    assert result.exit_code != 0


def test_flow_status_rejects_json_flag() -> None:
    """Test that flow status rejects the deprecated --json flag."""
    result = runner.invoke(app, ["flow", "status", "--json"])
    # Should fail with error (unknown option)
    assert result.exit_code != 0


# ==============================================================================
# Test: Default format (table)
# ==============================================================================


def test_flow_show_default_format() -> None:
    """Test flow show defaults to table format."""
    branch = "dev/issue-123"
    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status="active",
        task_issue_number=123,
        timeline=[],
        data_source=DataSource.LOCAL_SQLITE,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch("vibe3.services.FlowStatusResolver") as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                with patch(
                    "vibe3.commands.flow_status.render_flow_timeline"
                ) as mock_render:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service
                    mock_service.store.get_events.return_value = []

                    mock_resolver = MagicMock()
                    mock_resolver.resolve.return_value = flow_status
                    mock_resolver_class.return_value = mock_resolver

                    mock_projection = MagicMock()
                    mock_projection.get_issue_titles.return_value = ({}, None)
                    mock_projection_class.return_value = mock_projection

                    result = runner.invoke(app, ["flow", "show"])

                    assert result.exit_code == 0
                    # Should call render_flow_timeline (table output)
                    mock_render.assert_called_once()


def test_flow_status_default_format() -> None:
    """Test flow status defaults to table format."""
    mock_flows = [
        FlowStatusResponse(
            branch="dev/issue-123",
            flow_slug="dev-issue-123",
            flow_status="active",
            task_issue_number=123,
            timeline=[],
            data_source=DataSource.LOCAL_SQLITE,
        ),
    ]

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowProjectionService"
        ) as mock_projection_class:
            with patch(
                "vibe3.services.orchestra.status.OrchestraStatusService.fetch_live_snapshot",
                return_value=None,
            ):
                with patch(
                    "vibe3.commands.flow_status.render_flows_status_dashboard"
                ) as mock_render:
                    mock_service = MagicMock()
                    mock_service.list_flows.return_value = mock_flows
                    mock_service_class.return_value = mock_service

                    mock_projection = MagicMock()
                    mock_projection.get_issue_titles.return_value = ({}, None)
                    mock_projection_class.return_value = mock_projection

                    result = runner.invoke(app, ["flow", "status"])

                    assert result.exit_code == 0
                    # Should call render_flows_status_dashboard (table output)
                    mock_render.assert_called_once()
