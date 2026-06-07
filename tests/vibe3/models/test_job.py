"""Tests for job execution contracts."""

import pytest
from pydantic import ValidationError

from vibe3.models.job import (
    CommandType,
    JobContext,
    JobEnvelope,
    JobResult,
)


class TestCommandType:
    """Test CommandType enum."""

    def test_enum_values(self):
        """Verify all expected command types exist."""
        assert CommandType.PLAN == "plan"
        assert CommandType.RUN == "run"
        assert CommandType.REVIEW == "review"
        assert CommandType.MANAGER == "manager"
        assert CommandType.GOVERNANCE_SCAN == "governance-scan"
        assert CommandType.SUPERVISOR_APPLY == "supervisor-apply"

    def test_string_serialization(self):
        """Verify enum can be serialized to string."""
        assert CommandType.PLAN.value == "plan"
        assert CommandType.RUN.value == "run"

    def test_enum_from_string(self):
        """Verify enum can be constructed from string."""
        assert CommandType("plan") == CommandType.PLAN
        assert CommandType("run") == CommandType.RUN


class TestJobEnvelope:
    """Test JobEnvelope model."""

    def test_construction(self):
        """Verify basic envelope construction."""
        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123",
            source="cli-manual",
        )
        assert envelope.command_type == CommandType.PLAN
        assert envelope.issue_number == 123
        assert envelope.branch == "task/issue-123"
        assert envelope.source == "cli-manual"
        assert envelope.actor == "orchestra:system"  # default
        assert envelope.refs == {}  # default
        assert envelope.tick_id == 0  # default
        assert envelope.worktree_requirement == "none"  # default
        assert envelope.source_event_type is None
        assert envelope.adapter_path is None
        assert envelope.policy_hash is None
        assert envelope.material_hash is None

    def test_frozen_enforcement(self):
        """Verify envelope is immutable."""
        envelope = JobEnvelope(
            command_type=CommandType.RUN,
            issue_number=456,
            branch="task/issue-456",
            source="heartbeat-tick",
        )
        with pytest.raises(ValidationError, match="Instance is frozen"):
            envelope.issue_number = 789

    def test_model_dump_round_trip(self):
        """Verify serialization/deserialization round-trip."""
        original = JobEnvelope(
            command_type=CommandType.REVIEW,
            issue_number=789,
            branch="task/issue-789",
            source="cli-manual",
            actor="user:alice",
            refs={"plan_ref": "@plan-123"},
            tick_id=42,
            worktree_requirement="temporary",
        )
        data = original.model_dump()
        restored = JobEnvelope.model_validate(data)

        assert restored.command_type == CommandType.REVIEW
        assert restored.issue_number == 789
        assert restored.branch == "task/issue-789"
        assert restored.source == "cli-manual"
        assert restored.actor == "user:alice"
        assert restored.refs == {"plan_ref": "@plan-123"}
        assert restored.tick_id == 42
        assert restored.worktree_requirement == "temporary"

    def test_model_validate_round_trip(self):
        """Verify JSON round-trip."""
        original = JobEnvelope(
            command_type=CommandType.MANAGER,
            issue_number=999,
            branch="main",
            source="heartbeat-tick",
            source_event_type="ManagerDispatchIntent",
        )
        json_str = original.model_dump_json()
        restored = JobEnvelope.model_validate_json(json_str)

        assert restored.command_type == CommandType.MANAGER
        assert restored.issue_number == 999
        assert restored.source_event_type == "ManagerDispatchIntent"

    def test_optional_fields_default_to_none(self):
        """Verify optional fields default to None."""
        envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=1,
            branch="main",
            source="cli-manual",
        )
        assert envelope.source_event_type is None
        assert envelope.adapter_path is None
        assert envelope.policy_hash is None
        assert envelope.material_hash is None

    def test_refs_default_factory(self):
        """Verify refs defaults to empty dict."""
        envelope = JobEnvelope(
            command_type=CommandType.RUN,
            issue_number=1,
            branch="main",
            source="cli-manual",
        )
        assert envelope.refs == {}
        assert isinstance(envelope.refs, dict)


class TestJobContext:
    """Test JobContext model."""

    def test_construction(self):
        """Verify basic context construction."""
        context = JobContext(issue_number=123, branch="task/issue-123")
        assert context.issue_number == 123
        assert context.branch == "task/issue-123"
        assert context.tmux_session is None
        assert context.session_id is None
        assert context.log_path is None
        assert context.worktree_path is None
        assert context.cwd is None
        assert context.repo_path is None
        assert context.mode == "async"  # default

    def test_frozen_enforcement(self):
        """Verify context is immutable."""
        context = JobContext(issue_number=123, branch="main")
        with pytest.raises(ValidationError, match="Instance is frozen"):
            context.issue_number = 456

    def test_serialization_round_trip(self):
        """Verify serialization round-trip."""
        original = JobContext(
            issue_number=789,
            branch="task/issue-789",
            tmux_session="vibe-789",
            session_id="sess-123",
            log_path="/var/log/vibe/task-789.log",
            worktree_path="/tmp/worktree-789",
            cwd="/project",
            repo_path="/project",
            mode="sync",
        )
        data = original.model_dump()
        restored = JobContext.model_validate(data)

        assert restored.issue_number == 789
        assert restored.tmux_session == "vibe-789"
        assert restored.session_id == "sess-123"
        assert restored.log_path == "/var/log/vibe/task-789.log"
        assert restored.worktree_path == "/tmp/worktree-789"
        assert restored.cwd == "/project"
        assert restored.repo_path == "/project"
        assert restored.mode == "sync"


class TestJobResult:
    """Test JobResult model."""

    def test_construction(self):
        """Verify basic result construction."""
        result = JobResult(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123",
        )
        assert result.command_type == CommandType.PLAN
        assert result.issue_number == 123
        assert result.branch == "task/issue-123"
        assert result.status == "launched"  # default
        assert result.exit_code is None
        assert result.adapter_path is None
        assert result.context is None
        assert result.policy_hash is None
        assert result.material_hash is None
        assert result.payload_summary == {}
        assert result.started_at is None
        assert result.finished_at is None
        assert result.error_message is None
        assert result.error_code is None
        assert result.source is None

    def test_mutability(self):
        """Verify result is mutable (not frozen)."""
        result = JobResult(
            command_type=CommandType.RUN,
            issue_number=123,
            branch="main",
        )
        # Should not raise
        result.status = "completed"
        result.exit_code = 0
        assert result.status == "completed"
        assert result.exit_code == 0

    def test_serialization_round_trip(self):
        """Verify serialization round-trip."""
        context = JobContext(issue_number=123, branch="main")
        original = JobResult(
            command_type=CommandType.RUN,
            issue_number=123,
            branch="main",
            status="completed",
            exit_code=0,
            adapter_path="vibe3.execution.role_request_factory.build_run_async_request",
            context=context,
            payload_summary={"files_changed": "5"},
            started_at="2026-06-06T10:00:00Z",
            finished_at="2026-06-06T10:30:00Z",
            source="cli-manual",
        )
        data = original.model_dump()
        restored = JobResult.model_validate(data)

        assert restored.command_type == CommandType.RUN
        assert restored.status == "completed"
        assert restored.exit_code == 0
        assert restored.adapter_path is not None
        assert restored.context is not None
        assert restored.context.issue_number == 123
        assert restored.payload_summary == {"files_changed": "5"}
        assert restored.started_at == "2026-06-06T10:00:00Z"
        assert restored.finished_at == "2026-06-06T10:30:00Z"
        assert restored.source == "cli-manual"

    def test_status_transitions(self):
        """Verify status can transition from launched to completed/failed."""
        result = JobResult(
            command_type=CommandType.REVIEW,
            issue_number=123,
            branch="main",
            status="launched",
        )
        result.status = "completed"
        result.exit_code = 0
        assert result.status == "completed"

        failed_result = JobResult(
            command_type=CommandType.RUN,
            issue_number=456,
            branch="task/issue-456",
            status="launched",
        )
        failed_result.status = "failed"
        failed_result.error_message = "Test failure"
        assert failed_result.status == "failed"


class TestSemanticEquivalence:
    """Test semantic equivalence contract."""

    def test_envelopes_from_different_sources_produce_identical_core_payload(
        self,
    ):
        """
        Server-driven and CLI-driven execution of same command must produce
        semantically equivalent results (same command_type, issue_number,
        branch, refs).
        """
        # Server-driven envelope (heartbeat tick)
        server_envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123",
            source="heartbeat-tick",
            source_event_type="PlannerDispatchIntent",
            actor="orchestra:system",
            refs={"spec_ref": "@spec-123"},
            tick_id=42,
        )

        # CLI-driven envelope (manual)
        cli_envelope = JobEnvelope(
            command_type=CommandType.PLAN,
            issue_number=123,
            branch="task/issue-123",
            source="cli-manual",
            actor="user:alice",
            refs={"spec_ref": "@spec-123"},
            tick_id=42,
        )

        # Verify core payload is identical
        assert server_envelope.command_type == cli_envelope.command_type
        assert server_envelope.issue_number == cli_envelope.issue_number
        assert server_envelope.branch == cli_envelope.branch
        assert server_envelope.refs == cli_envelope.refs

        # Verify provenance differs
        assert server_envelope.source == "heartbeat-tick"
        assert cli_envelope.source == "cli-manual"
        assert server_envelope.source_event_type == "PlannerDispatchIntent"
        assert cli_envelope.source_event_type is None


class TestExistingPayloadRepresentation:
    """Test representing existing dispatch paths as JobEnvelope instances."""

    @pytest.mark.parametrize(
        "cmd_type,issue,branch,source,event_type,refs",
        [
            (
                CommandType.PLAN,
                123,
                "task/issue-123",
                "heartbeat-tick",
                "PlannerDispatchIntent",
                {"spec_ref": "@spec-123"},
            ),
            (
                CommandType.RUN,
                456,
                "task/issue-456",
                "heartbeat-tick",
                "ExecutorDispatchIntent",
                {"plan_ref": "@plan-456"},
            ),
            (
                CommandType.REVIEW,
                789,
                "task/issue-789",
                "heartbeat-tick",
                "ReviewerDispatchIntent",
                {"report_ref": "@report-789"},
            ),
            (
                CommandType.MANAGER,
                999,
                "main",
                "heartbeat-tick",
                "ManagerDispatchIntent",
                {"audit_ref": "@audit-999"},
            ),
            (CommandType.PLAN, 111, "task/issue-111", "cli-manual", None, {}),
            (CommandType.GOVERNANCE_SCAN, 0, "main", "heartbeat-tick", None, {}),
            (
                CommandType.SUPERVISOR_APPLY,
                222,
                "task/issue-222",
                "heartbeat-tick",
                "SupervisorApplyDispatchIntent",
                {},
            ),
            (
                CommandType.RUN,
                333,
                "task/issue-333",
                "cli-resume",
                None,
                {"session_id": "sess-333"},
            ),
        ],
    )
    def test_dispatch_intent_envelopes(
        self, cmd_type, issue, branch, source, event_type, refs
    ):
        """Represent dispatch intents as JobEnvelope instances."""
        envelope = JobEnvelope(
            command_type=cmd_type,
            issue_number=issue,
            branch=branch,
            source=source,
            source_event_type=event_type,
            refs=refs,
        )
        assert envelope.command_type == cmd_type
        assert envelope.source == source
        if event_type:
            assert envelope.source_event_type == event_type
