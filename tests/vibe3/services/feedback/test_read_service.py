"""Tests for FeedbackReadService."""

from __future__ import annotations

from pathlib import Path

import pytest

from vibe3.clients.feedback_store import FeedbackStore
from vibe3.models.audit_observation import AuditObservation, ObservationSourceWindow
from vibe3.services.feedback.read_service import FeedbackReadService
from vibe3.services.feedback.write_service import FeedbackWriteService


@pytest.fixture
def temp_store_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    import sqlite3

    from vibe3.clients.sqlite_schema import init_schema

    db_path = tmp_path / "feedback.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    return db_path


@pytest.fixture
def read_service(temp_store_path: Path) -> FeedbackReadService:
    """Create a read service with temporary store."""
    store = FeedbackStore(db_path=str(temp_store_path))
    return FeedbackReadService(store=store)


@pytest.fixture
def write_service(temp_store_path: Path) -> FeedbackWriteService:
    """Create a write service with temporary store."""
    store = FeedbackStore(db_path=str(temp_store_path))
    return FeedbackWriteService(store=store)


@pytest.fixture
def sample_observations(write_service: FeedbackWriteService) -> list[AuditObservation]:
    """Create sample observations for testing."""
    observations = []
    for i in range(5):
        obs = AuditObservation.create(
            observation_type=f"type_{i}",
            source_window=ObservationSourceWindow(
                issue_number=100 + i,
                branch=f"branch_{i}",
            ),
            symptom=f"Symptom {i}",
            observed_failure_mode="scope_mismatch" if i < 3 else "missing_output",
            confidence="high" if i % 2 == 0 else "low",
            created_by="test_suite",
            flow_status="blocked" if i < 2 else "failed",
        )
        # Customize some fields for filtering tests
        obs.source_material = f"source_{i % 2}"
        if i == 0:
            obs.next_stage_input["suggested_cluster_key"] = "cluster-a"
        elif i == 1:
            obs.next_stage_input["suggested_cluster_key"] = "cluster-a"
        else:
            obs.next_stage_input["suggested_cluster_key"] = "cluster-b"

        write_service.store.insert(obs)
        observations.append(obs)
    return observations


def test_list_all(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test listing all observations."""
    results = read_service.list_observations(limit=100)

    assert len(results) == 5


def test_list_filter_by_source(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test filtering by source material."""
    results = read_service.list_observations(source="source_0")

    assert len(results) == 3  # i=0, 2, 4


def test_list_filter_by_symptom(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test filtering by symptom substring."""
    results = read_service.list_observations(symptom="Symptom")

    assert len(results) == 5

    results = read_service.list_observations(symptom="Symptom 1")
    assert len(results) == 1


def test_list_filter_by_failure_mode(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test filtering by failure mode."""
    results = read_service.list_observations(failure_mode="scope_mismatch")

    assert len(results) == 3  # i=0, 1, 2


def test_list_with_limit(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test listing with limit."""
    results = read_service.list_observations(limit=2)

    assert len(results) == 2


def test_show_existing(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test showing an existing observation."""
    obs = sample_observations[0]
    result = read_service.show_observation(obs.observation_id)

    assert result is not None
    assert result["observation_id"] == obs.observation_id
    assert result["observation_type"] == obs.observation_type
    assert result["symptom"] == obs.symptom


def test_show_nonexistent(read_service: FeedbackReadService) -> None:
    """Test showing a nonexistent observation."""
    result = read_service.show_observation("nonexistent-id")

    assert result is None


def test_stats_by_failure_mode(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test stats aggregation by failure mode."""
    stats = read_service.get_stats(group_by="failure_mode")

    assert stats["scope_mismatch"] == 3
    assert stats["missing_output"] == 2


def test_stats_by_cluster_key(
    read_service: FeedbackReadService, sample_observations: list[AuditObservation]
) -> None:
    """Test stats aggregation by cluster key."""
    stats = read_service.get_stats(group_by="cluster_key")

    assert stats["cluster-a"] == 2  # i=0, 1
    assert stats["cluster-b"] == 3  # i=2, 3, 4


def test_stats_invalid_group_by(read_service: FeedbackReadService) -> None:
    """Test that invalid group_by raises ValueError."""
    with pytest.raises(ValueError):
        read_service.get_stats(group_by="invalid_field")


def test_list_empty(read_service: FeedbackReadService) -> None:
    """Test listing when no observations exist."""
    results = read_service.list_observations()

    assert len(results) == 0
