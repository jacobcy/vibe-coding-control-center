"""Tests for FlowStatusResponse data_source field."""

from vibe3.models.data_source import DataSource
from vibe3.models.flow import FlowStatusResponse


def test_flow_status_response_has_data_source_field():
    """FlowStatusResponse includes data_source for provenance tracking."""
    response = FlowStatusResponse(
        branch="dev/issue-123",
        flow_slug="issue-123",
        flow_status="active",
        data_source=DataSource.LOCAL_SQLITE,
    )
    assert response.data_source == DataSource.LOCAL_SQLITE


def test_flow_status_response_data_source_optional():
    """data_source is optional (None for backward compatibility)."""
    response = FlowStatusResponse(
        branch="dev/issue-123",
        flow_slug="issue-123",
        flow_status="active",
    )
    assert response.data_source is None
