"""Tests for audit observation data model."""

from __future__ import annotations

from vibe3.models import AuditObservation, ObservationSourceWindow


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

    def test_memory_ids_generic_description(self) -> None:
        """Test that memory_ids field description is generic."""
        field = ObservationSourceWindow.model_fields["memory_ids"]
        assert "NOT claude-mem specific" in field.description


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
            watermark="abc123def4567890",
        )

        assert obs_id.startswith("obs-")
        assert len(obs_id) > len("obs-")

    def test_observation_id_format(self) -> None:
        """Test observation ID has correct format."""
        obs_id = AuditObservation.compute_observation_id(
            timestamp="2024-01-01T00:00:00.000000",
            watermark="abc123def4567890",
        )

        # Should be: obs-<clean-timestamp>-<hash>
        # Clean timestamp removes :, -, . (but keeps T)
        assert "20240101T000000000000" in obs_id

    def test_create_factory_method(self) -> None:
        """Test AuditObservation.create() factory method."""
        source_window = ObservationSourceWindow(
            issue_number=123,
            branch="task/issue-123",
        )

        observation = AuditObservation.create(
            observation_type="flow_blocked",
            source_window=source_window,
            symptom="Flow blocked by dependency",
            observed_failure_mode="contract_missing",
            confidence="high",
            created_by="test",
        )

        assert observation.observation_type == "flow_blocked"
        assert observation.symptom == "Flow blocked by dependency"
        assert observation.observed_failure_mode == "contract_missing"
        assert observation.confidence == "high"
        assert observation.created_by == "test"
        assert observation.flow_status == "unknown"
        assert observation.facts == []
        assert observation.interpretation == {}
        assert observation.limitations == []
        assert observation.source_window.issue_number == 123
        assert observation.source_window.branch == "task/issue-123"

    def test_create_with_custom_fields(self) -> None:
        """Test factory method with custom fields."""
        source_window = ObservationSourceWindow(branch="test-branch")

        observation = AuditObservation.create(
            observation_type="memory_signal",
            source_window=source_window,
            symptom="Memory recurrence detected",
            observed_failure_mode="memory_signal",
            confidence="low",
            created_by="governance/audit-observation",
            flow_status="blocked",
            facts=[
                {
                    "kind": "memory",
                    "ref": "memory_ids: [123, 456]",
                    "summary": "Recurrence pattern found",
                }
            ],
            interpretation={
                "reasoning": "Similar symptoms observed in past flows",
            },
            limitations=["Could not verify exact memory source"],
        )

        assert observation.flow_status == "blocked"
        assert len(observation.facts) == 1
        assert observation.facts[0]["kind"] == "memory"
        assert (
            observation.interpretation["reasoning"]
            == "Similar symptoms observed in past flows"
        )
        assert len(observation.limitations) == 1

    def test_default_next_stage_input(self) -> None:
        """Test default next_stage_input structure."""
        source_window = ObservationSourceWindow(branch="test")
        observation = AuditObservation.create(
            observation_type="test",
            source_window=source_window,
            symptom="Test symptom",
            observed_failure_mode="unknown",
            confidence="medium",
            created_by="test",
        )

        assert observation.next_stage_input["suitable_for_clustering"] is True
        assert observation.next_stage_input["requires_human_review"] is True

    def test_model_validation_required_fields(self) -> None:
        """Test Pydantic validation catches missing required fields."""
        # This should raise ValidationError if required fields are missing
        # Factory method auto-generates IDs, so test direct construction
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AuditObservation(
                # Missing observation_id, observation_type, symptom, etc.
                source_window=ObservationSourceWindow(),
            )

    def test_model_validation_failure_mode_literal(self) -> None:
        """Test that observed_failure_mode must be from literal enum."""
        import pytest
        from pydantic import ValidationError

        source_window = ObservationSourceWindow(branch="test")

        with pytest.raises(ValidationError):
            AuditObservation(
                observation_id="obs-123",
                observation_type="test",
                source_window=source_window,
                symptom="Test",
                observed_failure_mode="invalid_mode",  # Not in literal
                confidence="high",
                created_by="test",
                created_at="2024-01-01T00:00:00",
                source_watermark="abc123",
            )

    def test_model_validation_confidence_literal(self) -> None:
        """Test that confidence must be from literal enum."""
        import pytest
        from pydantic import ValidationError

        source_window = ObservationSourceWindow(branch="test")

        with pytest.raises(ValidationError):
            AuditObservation(
                observation_id="obs-123",
                observation_type="test",
                source_window=source_window,
                symptom="Test",
                observed_failure_mode="unknown",
                confidence="extreme",  # Not in literal
                created_by="test",
                created_at="2024-01-01T00:00:00",
                source_watermark="abc123",
            )

    def test_serialization_roundtrip(self) -> None:
        """Test YAML ↔ Pydantic roundtrip serialization."""
        source_window = ObservationSourceWindow(
            issue_number=123,
            branch="task/issue-123",
            pr_number=456,
        )

        observation = AuditObservation.create(
            observation_type="flow_blocked",
            source_window=source_window,
            symptom="Test symptom",
            observed_failure_mode="contract_missing",
            confidence="high",
            created_by="test",
            facts=[{"kind": "flow", "ref": "branch", "summary": "Blocked"}],
        )

        # Serialize to dict (YAML-like)
        data = observation.model_dump()

        # Deserialize back
        observation2 = AuditObservation(**data)

        assert observation2.observation_id == observation.observation_id
        assert observation2.observation_type == observation.observation_type
        assert observation2.source_window.issue_number == 123
        assert observation2.source_window.branch == "task/issue-123"
        assert observation2.facts == observation.facts

    def test_watermark_auto_generated_by_factory(self) -> None:
        """Test that factory method auto-generates watermark."""
        source_window = ObservationSourceWindow(branch="test-branch")

        observation = AuditObservation.create(
            observation_type="test",
            source_window=source_window,
            symptom="Test",
            observed_failure_mode="unknown",
            confidence="medium",
            created_by="test",
        )

        # Watermark should be generated from branch
        assert observation.source_watermark is not None
        assert len(observation.source_watermark) == 16

    def test_observation_id_auto_generated_by_factory(self) -> None:
        """Test that factory method auto-generates observation ID."""
        source_window = ObservationSourceWindow(branch="test")

        observation = AuditObservation.create(
            observation_type="test",
            source_window=source_window,
            symptom="Test",
            observed_failure_mode="unknown",
            confidence="medium",
            created_by="test",
        )

        # Observation ID should be auto-generated
        assert observation.observation_id.startswith("obs-")
        assert len(observation.observation_id) > len("obs-")

    def test_source_material_default(self) -> None:
        """Test default source_material field."""
        source_window = ObservationSourceWindow(branch="test")
        observation = AuditObservation.create(
            observation_type="test",
            source_window=source_window,
            symptom="Test",
            observed_failure_mode="unknown",
            confidence="medium",
            created_by="test",
        )

        # Should have default source material
        assert observation.source_material == ".vibe/governance/audit-observation.md"
