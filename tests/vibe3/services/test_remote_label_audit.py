"""Tests for remote label audit functions (shared/labels.py)."""

from __future__ import annotations

from vibe3.services.shared.labels import (
    audit_multiple_state_labels,
    audit_orphan_execution_state,
    audit_orphan_orchestra_governed,
    audit_roadmap_state_conflict,
)


class TestAuditRoadmapStateConflict:
    """Rule 1: roadmap/rfc|epic + state/* → remove state labels."""

    def test_rfc_with_state(self) -> None:
        result = audit_roadmap_state_conflict(["roadmap/rfc", "state/claimed"])
        assert result == ["state/claimed"]

    def test_epic_with_multiple_states(self) -> None:
        result = audit_roadmap_state_conflict(
            ["roadmap/epic", "state/blocked", "state/review"]
        )
        assert set(result) == {"state/blocked", "state/review"}

    def test_rfc_without_state(self) -> None:
        assert audit_roadmap_state_conflict(["roadmap/rfc"]) == []

    def test_state_without_roadmap(self) -> None:
        assert audit_roadmap_state_conflict(["state/ready", "bug"]) == []

    def test_no_labels(self) -> None:
        assert audit_roadmap_state_conflict([]) == []


class TestAuditMultipleStateLabels:
    """Rule 2: multiple state/* → keep highest, remove others."""

    def test_blocked_and_review(self) -> None:
        result = audit_multiple_state_labels(["state/blocked", "state/review"])
        assert result == ["state/review"]  # blocked is higher priority

    def test_merge_ready_and_in_progress(self) -> None:
        result = audit_multiple_state_labels(["state/merge-ready", "state/in-progress"])
        assert result == ["state/in-progress"]

    def test_single_state(self) -> None:
        assert audit_multiple_state_labels(["state/ready"]) == []

    def test_no_state(self) -> None:
        assert audit_multiple_state_labels(["bug", "enhancement"]) == []

    def test_three_states(self) -> None:
        result = audit_multiple_state_labels(
            ["state/done", "state/review", "state/in-progress"]
        )
        assert set(result) == {"state/review", "state/in-progress"}  # done wins


class TestAuditOrphanExecutionState:
    """Rule 3: manager issue with execution state but no local flow."""

    def test_orphan_in_progress(self) -> None:
        removed, added = audit_orphan_execution_state(
            ["state/in-progress"], has_local_flow=False
        )
        assert removed == ["state/in-progress"]
        assert added == ["state/ready"]

    def test_has_local_flow(self) -> None:
        removed, added = audit_orphan_execution_state(
            ["state/in-progress"], has_local_flow=True
        )
        assert removed == []
        assert added == []

    def test_non_execution_state(self) -> None:
        removed, added = audit_orphan_execution_state(
            ["state/blocked"], has_local_flow=False
        )
        assert removed == []
        assert added == []

    def test_no_state(self) -> None:
        removed, added = audit_orphan_execution_state([], has_local_flow=False)
        assert removed == []
        assert added == []


class TestAuditOrphanOrchestraGoverned:
    """Rule 4: orchestra-governed without state/* or roadmap."""

    def test_orphan_orchestra(self) -> None:
        result = audit_orphan_orchestra_governed(["orchestra-governed"])
        assert result == ["orchestra-governed"]

    def test_with_state_label(self) -> None:
        result = audit_orphan_orchestra_governed(["orchestra-governed", "state/ready"])
        assert result == []

    def test_with_roadmap_label(self) -> None:
        result = audit_orphan_orchestra_governed(["orchestra-governed", "roadmap/rfc"])
        assert result == []

    def test_no_orchestra_label(self) -> None:
        assert audit_orphan_orchestra_governed(["bug"]) == []
