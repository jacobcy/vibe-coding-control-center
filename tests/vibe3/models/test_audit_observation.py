"""Tests for audit observation data model."""

from vibe3.models.audit_observation import (
    AuditObservation,
    ObservationSourceWindow,
)


class TestObservationSourceWindow:
    """Tests for ObservationSourceWindow model."""

    def test_create_with_all_fields(self) -> None:
        """Test creating source window with all fields."""
        window = ObservationSourceWindow(
            issue_number=123,
            branch="task/issue-123",
            pr_number=456,
            commit_shas=["abc123", "def456"],
            prompt_hash="hash123",
            skill_ids=["skill1", "skill2"],
            memory_ids=["mem1", "mem2"],
        )

        assert window.issue_number == 123
        assert window.branch == "task/issue-123"
        assert window.pr_number == 456
        assert window.commit_shas == ["abc123", "def456"]
        assert window.prompt_hash == "hash123"
        assert window.skill_ids == ["skill1", "skill2"]
        assert window.memory_ids == ["mem1", "mem2"]

    def test_create_with_defaults(self) -> None:
        """Test creating source window with default values."""
        window = ObservationSourceWindow(branch="test-branch")

        assert window.issue_number is None
        assert window.branch == "test-branch"
        assert window.pr_number is None
        assert window.commit_shas == []
        assert window.prompt_hash is None
        assert window.skill_ids == []
        assert window.memory_ids == []


class TestAuditObservation:
    """Tests for AuditObservation model."""

    def test_compute_watermark_basic(self) -> None:
        """Test watermark computation with minimal inputs."""
        watermark = AuditObservation.compute_watermark(
            branch="task/issue-123",
            updated_at=None,
            pr_number=None,
            prompt_hash=None,
        )

        assert isinstance(watermark, str)
        assert len(watermark) == 16

    def test_compute_watermark_with_all_fields(self) -> None:
        """Test watermark computation with all fields."""
        watermark1 = AuditObservation.compute_watermark(
            branch="task/issue-123",
            updated_at="2024-01-01T00:00:00",
            pr_number=456,
            prompt_hash="hash123",
        )

        watermark2 = AuditObservation.compute_watermark(
            branch="task/issue-123",
            updated_at="2024-01-01T00:00:00",
            pr_number=456,
            prompt_hash="hash456",  # Different hash
        )

        assert watermark1 != watermark2

    def test_compute_watermark_stability(self) -> None:
        """Test that same inputs produce same watermark."""
        watermark1 = AuditObservation.compute_watermark(
            branch="task/issue-123",
            updated_at="2024-01-01T00:00:00",
            pr_number=456,
            prompt_hash="hash123",
        )

        watermark2 = AuditObservation.compute_watermark(
            branch="task/issue-123",
            updated_at="2024-01-01T00:00:00",
            pr_number=456,
            prompt_hash="hash123",
        )

        assert watermark1 == watermark2

    def test_compute_observation_id(self) -> None:
        """Test observation ID generation."""
        obs_id = AuditObservation.compute_observation_id(
            timestamp="2024-01-01T00:00:00.000000",
            source_watermark="abc123def4567890",
        )

        assert obs_id.startswith("obs-")
        assert len(obs_id) > 10

    def test_create_observation(self) -> None:
        """Test observation creation with factory method."""
        source_window = ObservationSourceWindow(
            issue_number=123,
            branch="task/issue-123",
            pr_number=456,
        )

        observation = AuditObservation.create(
            observation_type="flow_blocked",
            source_window=source_window,
            symptom="Flow blocked by dependency",
            observed_failure_mode="contract_missing",
            confidence="high",
            created_by="test",
            flow_status="blocked",
            facts=[
                {
                    "kind": "flow",
                    "ref": "task/issue-123",
                    "summary": "Flow blocked",
                }
            ],
            interpretation={
                "reasoning": "Test reasoning",
                "likely_agent_failure": "",
                "affected_material_candidates": [],
                "affected_layer": "runtime",
            },
        )

        assert observation.observation_type == "flow_blocked"
        assert observation.symptom == "Flow blocked by dependency"
        assert observation.observed_failure_mode == "contract_missing"
        assert observation.confidence == "high"
        assert observation.created_by == "test"
        assert observation.flow_status == "blocked"
        assert len(observation.facts) == 1
        assert observation.facts[0]["kind"] == "flow"

    def test_observation_id_auto_generated(self) -> None:
        """Test that observation ID is auto-generated."""
        source_window = ObservationSourceWindow(branch="test-branch")

        observation = AuditObservation.create(
            observation_type="test",
            source_window=source_window,
            symptom="Test symptom",
            observed_failure_mode="unknown",
            confidence="low",
            created_by="test",
        )

        assert observation.observation_id.startswith("obs-")
        assert observation.source_watermark != ""

    def test_observation_defaults(self) -> None:
        """Test observation default values."""
        source_window = ObservationSourceWindow(branch="test-branch")

        observation = AuditObservation.create(
            observation_type="test",
            source_window=source_window,
            symptom="Test",
            observed_failure_mode="unknown",
            confidence="low",
            created_by="test",
        )

        assert observation.flow_status == "unknown"
        assert observation.facts == []
        assert observation.limitations == []
        assert observation.sample_count == 1
        assert (
            observation.source_material == "supervisor/governance/audit-observation.md"
        )

    def test_observation_mode_literal(self) -> None:
        """Test that observed_failure_mode accepts only valid values."""
        source_window = ObservationSourceWindow(branch="test-branch")

        # Valid modes
        for mode in [
            "scope_mismatch",
            "missing_output",
            "state_loop",
            "contract_missing",
            "ci_failure",
            "review_gap",
            "unknown",
        ]:
            observation = AuditObservation.create(
                observation_type="test",
                source_window=source_window,
                symptom="Test",
                observed_failure_mode=mode,  # type: ignore
                confidence="low",
                created_by="test",
            )
            assert observation.observed_failure_mode == mode

    def test_observation_serialization(self) -> None:
        """Test that observation can be serialized to dict."""
        source_window = ObservationSourceWindow(
            issue_number=123,
            branch="test-branch",
        )

        observation = AuditObservation.create(
            observation_type="test",
            source_window=source_window,
            symptom="Test symptom",
            observed_failure_mode="unknown",
            confidence="low",
            created_by="test",
        )

        # Should be able to serialize to dict
        obs_dict = observation.model_dump()

        assert isinstance(obs_dict, dict)
        assert obs_dict["observation_type"] == "test"
        assert obs_dict["symptom"] == "Test symptom"
        assert obs_dict["observed_failure_mode"] == "unknown"
