"""Handoff service implementation."""

from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.exceptions import UserError
from vibe3.execution.actor_support import (
    extract_role_from_actor,
)
from vibe3.models.flow import FlowEvent
from vibe3.models.verdict import VerdictRecord
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.handoff_storage import HandoffStorage
from vibe3.services.signature_service import SignatureService
from vibe3.utils.path_helpers import (
    _SHARED_HANDOFF_PREFIX,
    GitClientProtocol,
)


class HandoffService:
    """Service for managing handoff records."""

    _AUTHORITATIVE_REF_KINDS = {"plan", "report", "audit"}
    _HANDOFF_EVENT_TYPES = {
        "handoff_plan",
        "handoff_report",
        "handoff_run",
        "handoff_audit",
        "handoff_indicate",
        "plan_recorded",
        "run_recorded",
        "audit_recorded",
    }

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

        Handoff views should only show explicit handoff artifacts / verdict events.
        Runtime lifecycle and flow state events belong to `flow show`, not
        `handoff status`.

        Note: Both active events (handoff_plan/run/audit) and passive events
        (*_recorded) are included. Passive events serve as fallback records when
        active writes fail, so they should not be filtered out.
        """
        events_data = self.store.get_events(branch, event_type_prefix=event_type_prefix)
        handoff_events = [
            FlowEvent(**event)
            for event in events_data
            if event["event_type"] in self._HANDOFF_EVENT_TYPES
        ]
        if limit is not None:
            handoff_events = handoff_events[:limit]
        return handoff_events

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

    def _resolve_branch_worktree_root(self, branch: str) -> Path:
        worktree_root = self.git_client.find_worktree_path_for_branch(branch)
        if worktree_root is not None:
            return worktree_root

        current_root = self.git_client.get_worktree_root()
        if current_root:
            return Path(current_root)

        raise UserError("Cannot validate handoff ref without a worktree root")

    @staticmethod
    def _is_log_like_path(path: Path) -> bool:
        lowered_parts = [part.lower() for part in path.parts]
        for idx in range(len(lowered_parts) - 1):
            if lowered_parts[idx] == "temp" and lowered_parts[idx + 1] == "logs":
                return True
        return path.name.endswith(".async.log")

    def _validate_authoritative_ref(
        self, ref_kind: str, ref_value: str, branch: str
    ) -> None:
        if ref_kind.lower() not in self._AUTHORITATIVE_REF_KINDS:
            return

        worktree_root = self._resolve_branch_worktree_root(branch).resolve()
        ref_path = Path(ref_value).expanduser()
        resolved = (
            ref_path.resolve(strict=False)
            if ref_path.is_absolute()
            else (worktree_root / ref_path).resolve(strict=False)
        )

        if self._is_log_like_path(resolved):
            raise UserError(
                f"{ref_kind}_ref cannot point to execution logs under temp/logs: "
                f"{ref_value}"
            )
        git_common = Path(self.git_client.get_git_common_dir()).resolve()
        if resolved.is_relative_to(git_common):
            raise UserError(
                f"{ref_kind}_ref must point to an agent worktree document, "
                f"not shared handoff store: {ref_value}"
            )
        if not resolved.is_relative_to(worktree_root):
            raise UserError(
                f"{ref_kind}_ref must stay inside the agent worktree: {ref_value}"
            )

    def _record_ref(
        self,
        ref_kind: str,
        ref_value: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str | None,
        verdict: str | None = None,
        audit_is_system_auto: bool = False,
    ) -> Path:
        """Internal helper to record a handoff reference."""
        branch = self.git_client.get_current_branch()
        self._validate_authoritative_ref(ref_kind, ref_value, branch)
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

        message = f"Recorded {ref_kind} reference: {ref_value}"
        if verdict:
            message = f"verdict: {verdict}\n{message}"
        if next_step:
            message += f"\nNext Step: {next_step}"
        if blocked_by:
            message += f"\nBlocked By: {blocked_by}"

        self.store.update_flow_state(branch, **flow_updates)

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
    ) -> Path:
        """Record manager indicate handoff reference."""
        return self._record_ref("indicate", indicate_ref, next_step, blocked_by, actor)

    def record_passive_artifact(
        self,
        *,
        kind: str,
        content: str,
        actor: str | None = None,
        metadata: dict[str, str] | None = None,
        branch: str | None = None,
    ) -> Path | None:
        """Record a shared fallback artifact without upgrading authoritative refs."""
        if kind not in {"plan", "run"}:
            raise UserError(f"Unsupported passive artifact kind: {kind}")

        target_branch = branch or self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            target_branch,
            explicit_actor=actor,
        )
        sanitized_content = ArtifactParser.sanitize_handoff_content(content).strip()
        if not sanitized_content:
            return None

        created = self.storage.create_artifact(
            prefix=kind,
            content=sanitized_content + "\n",
            branch=target_branch,
        )
        if created is None:
            return None
        _, artifact_path = created

        detail, extra_refs = ArtifactParser.build_artifact_detail(
            kind,
            sanitized_content,
            artifact_path,
            metadata=metadata,
        )
        event_type = f"{kind}_recorded"
        git_common = Path(self.git_client.get_git_common_dir())
        relative_ref = (
            str(artifact_path.relative_to(git_common))
            if artifact_path.is_absolute()
            else str(artifact_path)
        )
        # Normalize to @ prefix format for shared handoff artifacts
        # vibe3/handoff/task-xxx/plan.md → @task-xxx/plan.md
        if relative_ref.startswith(_SHARED_HANDOFF_PREFIX):
            ref_value = "@" + relative_ref[len(_SHARED_HANDOFF_PREFIX) :]
        else:
            ref_value = relative_ref
        refs: dict[str, str | list[str]] = {"ref": ref_value}
        refs.update(extra_refs)
        self.store.add_event(
            target_branch,
            event_type,
            effective_actor,
            detail=detail,
            refs=refs,
        )
        return artifact_path
