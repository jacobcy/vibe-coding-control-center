"""Tests for flow status --remote timeline source behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.data_source import DataSource
from vibe3.models.flow import FlowStatusResponse, TimelineEvent

runner = CliRunner()


def test_remote_no_local_db_uses_remote_timeline() -> None:
    """No local flow/events, --remote <issue> renders timeline from issue comments."""
    issue_number = 1423
    branch = f"remote-#{issue_number}"

    # Mock timeline events from GitHub comments
    timeline_events = [
        TimelineEvent(
            timestamp="2024-01-01T10:00:00Z",
            event_type="flow_created",
            actor="alice",
            detail="Flow created",
        ),
        TimelineEvent(
            timestamp="2024-01-02T11:00:00Z",
            event_type="state_transitioned",
            actor="bob",
            detail="state/in-progress",
        ),
    ]

    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status="active",
        task_issue_number=issue_number,
        timeline=timeline_events,
        data_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowStatusResolver"
        ) as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                with patch(
                    "vibe3.commands.flow_status.render_flow_timeline"
                ) as mock_render:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_resolver = MagicMock()
                    mock_resolver.resolve.return_value = flow_status
                    mock_resolver_class.return_value = mock_resolver

                    mock_projection = MagicMock()
                    mock_projection.get_issue_titles.return_value = ({}, None)
                    mock_projection_class.return_value = mock_projection

                    result = runner.invoke(
                        app, ["flow", "show", "--remote", str(issue_number)]
                    )

                    assert result.exit_code == 0
                    # Verify resolver was called with remote=True
                    mock_resolver.resolve.assert_called_once()
                    call_kwargs = mock_resolver.resolve.call_args.kwargs
                    assert call_kwargs["remote"] is True
                    assert call_kwargs["issue_number"] == issue_number

                    # Verify timeline was rendered (not local events)
                    mock_render.assert_called_once()
                    rendered_events = mock_render.call_args.args[1]
                    assert len(rendered_events) == 2
                    assert rendered_events[0].event_type == "flow_created"
                    assert rendered_events[0].actor == "alice"
                    assert rendered_events[1].event_type == "state_transitioned"
                    assert rendered_events[1].actor == "bob"


def test_remote_ignores_stale_local_events() -> None:
    """Local DB has stale events, --remote still uses remote timeline."""
    issue_number = 1423
    branch = f"remote-#{issue_number}"

    # Remote timeline (fresh)
    remote_timeline = [
        TimelineEvent(
            timestamp="2024-01-03T10:00:00Z",
            event_type="flow_created",
            actor="alice",
            detail="Flow created (remote)",
        ),
    ]

    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status="active",
        task_issue_number=issue_number,
        timeline=remote_timeline,
        data_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowStatusResolver"
        ) as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                with patch(
                    "vibe3.commands.flow_status.render_flow_timeline"
                ) as mock_render:
                    mock_service = MagicMock()
                    # Simulate local DB with stale events
                    mock_store = MagicMock()
                    mock_store.get_events.return_value = [
                        {
                            "branch": branch,
                            "event_type": "flow_created",
                            "actor": "old_actor",
                            "detail": "Stale local event",
                            "created_at": "2024-01-01T00:00:00Z",
                        }
                    ]
                    mock_service.store = mock_store
                    mock_service_class.return_value = mock_service

                    mock_resolver = MagicMock()
                    mock_resolver.resolve.return_value = flow_status
                    mock_resolver_class.return_value = mock_resolver

                    mock_projection = MagicMock()
                    mock_projection.get_issue_titles.return_value = ({}, None)
                    mock_projection_class.return_value = mock_projection

                    result = runner.invoke(
                        app, ["flow", "show", "--remote", str(issue_number)]
                    )

                    assert result.exit_code == 0
                    # Verify remote timeline was used, not local DB
                    mock_render.assert_called_once()
                    rendered_events = mock_render.call_args.args[1]
                    assert len(rendered_events) == 1
                    assert rendered_events[0].actor == "alice"
                    assert rendered_events[0].detail == "Flow created (remote)"
                    # Local DB should NOT have been queried
                    mock_store.get_events.assert_not_called()


def test_non_remote_uses_local_events() -> None:
    """flow show without --remote uses local SQLite events."""
    branch = "task/demo"

    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug="demo",
        flow_status="active",
        task_issue_number=123,
        timeline=[],  # Empty timeline
        data_source=DataSource.LOCAL_SQLITE,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowStatusResolver"
        ) as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                with patch(
                    "vibe3.commands.flow_status.render_flow_timeline"
                ) as mock_render:
                    with patch(
                        "vibe3.commands.flow_status.resolve_command_branch"
                    ) as mock_resolve_branch:
                        mock_service = MagicMock()
                        mock_store = MagicMock()
                        mock_store.get_issue_links.return_value = [
                            {"issue_role": "task", "issue_number": 123}
                        ]
                        mock_store.get_events.return_value = [
                            {
                                "branch": branch,
                                "event_type": "flow_created",
                                "actor": "local_actor",
                                "detail": "Local event",
                                "created_at": "2024-01-01T00:00:00Z",
                            }
                        ]
                        mock_service.store = mock_store
                        mock_service_class.return_value = mock_service

                        mock_resolve_branch.return_value = branch

                        mock_resolver = MagicMock()
                        mock_resolver.resolve.return_value = flow_status
                        mock_resolver_class.return_value = mock_resolver

                        mock_projection = MagicMock()
                        mock_projection.get_issue_titles.return_value = ({}, None)
                        mock_projection_class.return_value = mock_projection

                        result = runner.invoke(app, ["flow", "show"])

                        assert result.exit_code == 0
                        # Verify local events were queried
                        mock_store.get_events.assert_called_once_with(branch, limit=100)
                        # Verify local events were used for rendering
                        mock_render.assert_called_once()
                        rendered_events = mock_render.call_args.args[1]
                        assert len(rendered_events) == 1
                        assert rendered_events[0].actor == "local_actor"


def test_remote_json_output_includes_timeline() -> None:
    """--format json --remote <issue> includes remote timeline data."""
    issue_number = 1423
    branch = f"remote-#{issue_number}"

    timeline_events = [
        TimelineEvent(
            timestamp="2024-01-01T10:00:00Z",
            event_type="flow_created",
            actor="alice",
            detail="Flow created",
        ),
    ]

    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status="active",
        task_issue_number=issue_number,
        timeline=timeline_events,
        data_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowStatusResolver"
        ) as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                mock_service = MagicMock()
                mock_service_class.return_value = mock_service

                mock_resolver = MagicMock()
                mock_resolver.resolve.return_value = flow_status
                mock_resolver_class.return_value = mock_resolver

                mock_projection = MagicMock()
                mock_projection.get_issue_titles.return_value = ({}, None)
                mock_projection_class.return_value = mock_projection

                result = runner.invoke(
                    app,
                    ["flow", "show", "--remote", str(issue_number), "--format", "json"],
                )

                assert result.exit_code == 0
                import json

                output = json.loads(result.output)
                assert "events" in output
                assert len(output["events"]) == 1
                assert output["events"][0]["event_type"] == "flow_created"
                assert output["events"][0]["actor"] == "alice"


def test_remote_yaml_output_includes_timeline() -> None:
    """--format yaml --remote <issue> includes remote timeline data."""
    issue_number = 1423
    branch = f"remote-#{issue_number}"

    timeline_events = [
        TimelineEvent(
            timestamp="2024-01-01T10:00:00Z",
            event_type="flow_created",
            actor="alice",
            detail="Flow created",
        ),
    ]

    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status="active",
        task_issue_number=issue_number,
        timeline=timeline_events,
        data_source=DataSource.ISSUE_BODY_FALLBACK,
    )

    with patch("vibe3.commands.flow_status.FlowService") as mock_service_class:
        with patch(
            "vibe3.commands.flow_status.FlowStatusResolver"
        ) as mock_resolver_class:
            with patch(
                "vibe3.commands.flow_status.FlowProjectionService"
            ) as mock_projection_class:
                mock_service = MagicMock()
                mock_service_class.return_value = mock_service

                mock_resolver = MagicMock()
                mock_resolver.resolve.return_value = flow_status
                mock_resolver_class.return_value = mock_resolver

                mock_projection = MagicMock()
                mock_projection.get_issue_titles.return_value = ({}, None)
                mock_projection_class.return_value = mock_projection

                result = runner.invoke(
                    app,
                    ["flow", "show", "--remote", str(issue_number), "--format", "yaml"],
                )

                assert result.exit_code == 0
                assert "flow_created" in result.output
                assert "alice" in result.output


def test_remote_without_issue_number_errors() -> None:
    """flow show --remote without argument raises clear UserError."""
    result = runner.invoke(app, ["flow", "show", "--remote"])

    assert result.exit_code != 0
    # Check exception message instead of output (UserError is raised, not printed)
    assert result.exception is not None
    assert "Cannot use --remote without an issue number" in str(result.exception)
