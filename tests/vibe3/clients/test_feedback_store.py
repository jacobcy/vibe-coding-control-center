"""Tests for FeedbackStore database operations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibe3.clients.feedback_store import FeedbackStore
from vibe3.models.audit_observation import AuditObservation, ObservationSourceWindow


@pytest.fixture
def temp_feedback_store(tmp_path: Path) -> FeedbackStore:
    """Create a temporary FeedbackStore for testing."""
    import sqlite3

    from vibe3.clients.sqlite_schema import init_schema

    db_path = tmp_path / "feedback.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    return FeedbackStore(db_path=str(db_path))


@pytest.fixture
def sample_observation() -> AuditObservation:
    """Create a sample observation for testing."""
    return AuditObservation.create(
        observation_type="test_observation",
        source_window=ObservationSourceWindow(
            issue_number=123,
            branch="test/branch",
            pr_number=456,
        ),
        symptom="Test symptom",
        observed_failure_mode="scope_mismatch",
        confidence="high",
        created_by="test_suite",
        flow_status="blocked",
        facts=[{"kind": "test", "ref": "ref1", "summary": "Test fact"}],
        interpretation={
            "reasoning": "Test reasoning",
            "likely_agent_failure": "Test failure",
        },
        limitations=["Test limitation"],
        next_stage_input={
            "suitable_for_clustering": True,
            "suggested_cluster_key": "test-cluster",
            "requires_human_review": True,
        },
    )


def test_insert_and_retrieve(
    temp_feedback_store: FeedbackStore, sample_observation: AuditObservation
) -> None:
    """Test basic insert and retrieve by ID."""
    # Insert
    obs_id = temp_feedback_store.insert(sample_observation)
    assert obs_id == sample_observation.observation_id

    # Retrieve
    retrieved = temp_feedback_store.get_by_id(obs_id)
    assert retrieved is not None
    assert retrieved["observation_id"] == sample_observation.observation_id
    assert retrieved["observation_type"] == "test_observation"
    assert retrieved["symptom"] == "Test symptom"
    assert retrieved["observed_failure_mode"] == "scope_mismatch"
    assert retrieved["confidence"] == "high"
    assert retrieved["flow_status"] == "blocked"
    assert retrieved["subject_issue_number"] == 123
    assert retrieved["subject_branch"] == "test/branch"
    assert retrieved["subject_pr_number"] == 456


def test_insert_dedup_by_watermark(
    temp_feedback_store: FeedbackStore, sample_observation: AuditObservation
) -> None:
    """Test that duplicate observations are skipped based on watermark."""
    # First insert
    obs_id_1 = temp_feedback_store.insert(sample_observation)

    # Create another observation with same watermark
    obs2 = AuditObservation.create(
        observation_type="different_type",
        source_window=ObservationSourceWindow(
            issue_number=999,
            branch="different/branch",
        ),
        symptom="Different symptom",
        observed_failure_mode="missing_output",
        confidence="low",
        created_by="test_suite",
    )
    # Force same watermark
    obs2.source_watermark = sample_observation.source_watermark

    # Second insert should be skipped
    obs_id_2 = temp_feedback_store.insert(obs2)
    assert obs_id_2 == obs_id_1  # Returns existing ID

    # Verify only one record exists
    all_obs = temp_feedback_store.list_observations(limit=100)
    assert len(all_obs) == 1


def test_list_with_filters(temp_feedback_store: FeedbackStore) -> None:
    """Test list observations with various filters."""
    # Insert multiple observations
    for i in range(5):
        obs = AuditObservation.create(
            observation_type=f"type_{i}",
            source_window=ObservationSourceWindow(branch=f"branch_{i}"),
            symptom=f"Symptom {i}",
            observed_failure_mode="scope_mismatch" if i < 3 else "missing_output",
            confidence="high" if i % 2 == 0 else "low",
            created_by="test_suite",
        )
        obs.source_material = f"source_{i % 2}"
        temp_feedback_store.insert(obs)

    # Filter by source
    results = temp_feedback_store.list_observations(source="source_0")
    assert len(results) == 3  # i=0, 2, 4

    # Filter by failure_mode
    results = temp_feedback_store.list_observations(failure_mode="scope_mismatch")
    assert len(results) == 3  # i=0, 1, 2

    # Filter by symptom substring
    results = temp_feedback_store.list_observations(symptom="Symptom")
    assert len(results) == 5

    # Limit
    results = temp_feedback_store.list_observations(limit=2)
    assert len(results) == 2


def test_get_stats_by_failure_mode(temp_feedback_store: FeedbackStore) -> None:
    """Test statistics aggregation by failure mode."""
    # Insert observations with different failure modes
    for i in range(10):
        obs = AuditObservation.create(
            observation_type=f"type_{i}",
            source_window=ObservationSourceWindow(branch=f"branch_{i}"),
            symptom=f"Symptom {i}",
            observed_failure_mode="scope_mismatch" if i < 5 else "missing_output",
            confidence="high",
            created_by="test_suite",
        )
        temp_feedback_store.insert(obs)

    stats = temp_feedback_store.get_stats(group_by="failure_mode")
    assert stats["scope_mismatch"] == 5
    assert stats["missing_output"] == 5


def test_get_stats_by_cluster_key(temp_feedback_store: FeedbackStore) -> None:
    """Test statistics aggregation by cluster key."""
    # Insert observations with different cluster keys
    for i in range(8):
        obs = AuditObservation.create(
            observation_type=f"type_{i}",
            source_window=ObservationSourceWindow(branch=f"branch_{i}"),
            symptom=f"Symptom {i}",
            observed_failure_mode="scope_mismatch",
            confidence="high",
            created_by="test_suite",
            next_stage_input={
                "suitable_for_clustering": True,
                "suggested_cluster_key": "cluster-a" if i < 3 else "cluster-b",
            },
        )
        temp_feedback_store.insert(obs)

    stats = temp_feedback_store.get_stats(group_by="cluster_key")
    assert stats["cluster-a"] == 3
    assert stats["cluster-b"] == 5


def test_json_fields_serialization(temp_feedback_store: FeedbackStore) -> None:
    """Test that JSON fields are correctly serialized and deserialized."""
    obs = AuditObservation.create(
        observation_type="json_test",
        source_window=ObservationSourceWindow(
            branch="test",
            commit_shas=["sha1", "sha2"],
            skill_ids=["skill1", "skill2"],
            memory_ids=["mem1", "mem2"],
        ),
        symptom="JSON test",
        observed_failure_mode="scope_mismatch",
        confidence="high",
        created_by="test_suite",
        facts=[{"kind": "flow", "ref": "ref", "summary": "sum"}],
        interpretation={
            "reasoning": "test",
            "affected_material_candidates": ["mat1", "mat2"],
        },
        limitations=["lim1", "lim2"],
    )

    temp_feedback_store.insert(obs)
    retrieved = temp_feedback_store.get_by_id(obs.observation_id)

    assert retrieved is not None
    # Check JSON fields are correctly serialized
    assert json.loads(retrieved["subject_commit_shas"]) == ["sha1", "sha2"]
    assert json.loads(retrieved["subject_skill_ids"]) == ["skill1", "skill2"]
    assert json.loads(retrieved["subject_memory_ids"]) == ["mem1", "mem2"]
    assert json.loads(retrieved["facts"]) == [
        {"kind": "flow", "ref": "ref", "summary": "sum"}
    ]
    assert json.loads(retrieved["limitations"]) == ["lim1", "lim2"]
