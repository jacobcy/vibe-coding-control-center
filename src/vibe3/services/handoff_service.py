"""Handoff service implementation."""

from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.execution.actor_support import (
    extract_role_from_actor,
    format_agent_actor,
    resolve_actor_backend_model,
)
from vibe3.execution.role_policy import get_optional_kind_actor_key
from vibe3.models.flow import FlowEvent
from vibe3.models.handoff import HandoffRecord
from vibe3.models.verdict import VerdictRecord
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.handoff_storage import HandoffStorage
from vibe3.services.signature_service import SignatureService
from vibe3.utils.path_helpers import (
    GitClientProtocol,
)


class HandoffService:
    """Service for managing handoff records."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClientProtocol | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.storage = HandoffStorage(self.git_client)

    def get_handoff_events(
        self,
        branch: str,
        event_type_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[FlowEvent]:
        """Return handoff events for a branch from the authoritative store.

        Note: does NOT filter by prefix by default — the caller (handoff_read)
        is responsible for keeping only known handoff event types via its
        whitelist map. Filtering here with "handoff_" would silently drop
        "audit_recorded" events which do not share that prefix.
        """
        events_data = self.store.get_events(
            branch, event_type_prefix=event_type_prefix, limit=limit
        )
        return [FlowEvent(**event) for event in events_data]

    def append_current_handoff(
        self,
        message: str,
        actor: str | None,
        kind: str = "note",
    ) -> Path:
        """Append a lightweight update block to current.md."""
        branch = self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )
        return self.storage.append_current_handoff(message, effective_actor, kind)

    def _record_ref(
        self,
        ref_kind: str,
        ref_value: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str | None,
        verdict: str | None = None,
        audit_is_system_auto: bool = False,
        action: str | None = None,
    ) -> Path:
        """Internal helper to record a handoff reference."""
        branch = self.git_client.get_current_branch()
        # Inlined _normalize_ref_value
        ref_value = self.storage.normalize_ref_value(ref_value, branch)
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )

        handoff_path = self.storage.ensure_current_handoff()

        ref_field = f"{ref_kind.lower()}_ref"

        # Build flow state updates
        flow_updates = {ref_field: ref_value}
        actor_field_by_kind = {
            "plan": "planner_actor",
            "report": "executor_actor",
            "audit": "reviewer_actor",
        }
        actor_field = actor_field_by_kind.get(ref_kind.lower())
        if actor_field:
            flow_updates[actor_field] = effective_actor
        if next_step:
            flow_updates["next_step"] = next_step
        if blocked_by:
            flow_updates["blocked_by"] = blocked_by

        if verdict:
            role = extract_role_from_actor(effective_actor)
            record = VerdictRecord(
                verdict=verdict,  # type: ignore
                actor=effective_actor,
                role=role,
                timestamp=datetime.now(UTC),
                reason=next_step or f"Recorded {ref_kind} reference",
                issues=blocked_by,
                flow_branch=branch,
            )
            flow_updates["latest_verdict"] = record.model_dump_json()

        message = f"verdict: {verdict or 'UNKNOWN'}"
        message += f"\nRecorded {ref_kind} reference: {ref_value}"
        if next_step:
            message += f"\nNext Step: {next_step}"
        if blocked_by:
            message += f"\nBlocked By: {blocked_by}"

        self.store.update_flow_state(branch, **flow_updates)

        if ref_kind.lower() == "indicate":
            self.store.update_flow_state(
                branch, latest_indicate_action=action  # None clears the field
            )

        event_refs: dict[str, str] = {"ref": ref_value}
        if verdict:
            event_refs["verdict"] = verdict

        event_type = (
            "audit_recorded"
            if ref_kind.lower() == "audit" and audit_is_system_auto
            else (
                "handoff_audit"
                if ref_kind.lower() == "audit"
                else f"handoff_{ref_kind.lower()}"
            )
        )
        self.store.add_event(
            branch,
            event_type,
            effective_actor,
            detail=message,
            refs=event_refs,
        )

        try:
            self.append_current_handoff(
                message=message,
                actor=effective_actor,
                kind=ref_kind.lower(),
            )
        except (OSError, PermissionError) as exc:
            logger.bind(
                domain="handoff",
                action="append_current_handoff_best_effort",
                branch=branch,
                ref_kind=ref_kind.lower(),
                handoff_path=str(handoff_path),
            ).warning(f"Skipping non-authoritative handoff file append: {exc}")

        return handoff_path

    def record_agent_artifact(self, record: HandoffRecord) -> Path | None:
        """Persist a plan/run/review artifact and corresponding handoff event."""
        sanitized_content = ArtifactParser.sanitize_handoff_content(record.content)
        artifact = self.storage.create_artifact(
            record.kind,
            sanitized_content,
            branch=record.branch,
        )
        if artifact is None:
            return None

        branch, artifact_file = artifact
        actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=format_agent_actor(record.options),
        )
        backend, model = resolve_actor_backend_model(record.options)

        detail, derived_refs = ArtifactParser.build_artifact_detail(
            record.kind, sanitized_content, artifact_file, record.metadata
        )
        # Inlined _normalize_ref_value
        normalized_ref = self.storage.normalize_ref_value(str(artifact_file), branch)
        refs: dict[str, str] = {
            "ref": normalized_ref,
            "backend": backend,
            **derived_refs,
        }
        if model:
            refs["model"] = model
        if record.session_id:
            refs["session_id"] = record.session_id

        if record.log_path:
            # Inlined _normalize_ref_value
            normalized_log = self.storage.normalize_ref_value(record.log_path, branch)
            refs["log_path"] = normalized_log

        flow_state_updates: dict[str, object] = {}
        actor_key = get_optional_kind_actor_key(record.kind)
        if actor_key is not None:
            flow_state_updates[actor_key] = actor

        if record.kind == "run":
            event_type = "handoff_report"
        else:
            event_type = f"handoff_{record.kind}"

        # Inlined persist_artifact_event
        self.store.add_event(branch, event_type, actor, detail=detail, refs=refs)
        if flow_state_updates:
            self.store.update_flow_state(branch, **flow_state_updates)

        return artifact_file

    def record_plan(
        self,
        plan_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
    ) -> Path:
        """Record plan handoff reference."""
        return self._record_ref("plan", plan_ref, next_step, blocked_by, actor)

    def record_report(
        self,
        report_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
    ) -> Path:
        """Record report handoff reference."""
        return self._record_ref("report", report_ref, next_step, blocked_by, actor)

    def record_audit(
        self,
        audit_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
        verdict: str | None = None,
        is_system_auto: bool = False,
    ) -> Path:
        """Record audit handoff reference."""
        return self._record_ref(
            "audit",
            audit_ref,
            next_step,
            blocked_by,
            actor,
            verdict=verdict,
            audit_is_system_auto=is_system_auto,
        )

    def record_indicate(
        self,
        indicate_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
        action: str | None = None,
    ) -> Path:
        """Record manager indicate handoff reference."""
        return self._record_ref(
            "indicate", indicate_ref, next_step, blocked_by, actor, action=action
        )
