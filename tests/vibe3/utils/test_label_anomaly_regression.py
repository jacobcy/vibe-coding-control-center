"""Regression tests for shared label anomaly rules."""

from vibe3.clients import collect_label_anomalies
from vibe3.services.shared.labels import has_roadmap_label


def test_priority_roadmap_is_not_lifecycle_roadmap() -> None:
    assert has_roadmap_label(["roadmap/p1", "state/ready"]) is False


def test_priority_roadmap_does_not_remove_state() -> None:
    result = collect_label_anomalies(
        ["roadmap/p1", "state/ready"],
        issue_number=1,
        has_local_flow=True,
        is_manager_issue=True,
    )
    assert result == []


def test_orphan_merge_ready_is_reset_to_ready() -> None:
    result = collect_label_anomalies(
        ["state/merge-ready"],
        issue_number=1,
        has_local_flow=False,
        is_manager_issue=True,
    )
    assert len(result) == 1
    assert "orphan_execution" in result[0].rule
    assert result[0].removed == ["state/merge-ready"]
    assert result[0].added == ["state/ready"]


def test_orphan_blocked_is_not_reset_to_ready() -> None:
    result = collect_label_anomalies(
        ["state/blocked"],
        issue_number=1,
        has_local_flow=False,
        is_manager_issue=True,
    )
    assert result == []
