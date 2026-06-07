"""Handoff service implementation."""

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, cast

from loguru import logger

from vibe3.clients import GitClient, SQLiteClient
from vibe3.exceptions import UserError
from vibe3.models import FlowEvent, VerdictRecord
from vibe3.services.actor_support import (
    extract_role_from_actor,
)
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.external_events import ExternalEventRecorder
from vibe3.services.git_path_client import GitPathProtocol
from vibe3.services.handoff_storage import HandoffStorage
from vibe3.services.handoff_validation import validate_authoritative_ref
from vibe3.services.path_helpers import _SHARED_HANDOFF_PREFIX
from vibe3.services.signature_service import SignatureService

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient


class HandoffService:
    """Service for managing handoff records."""

    # Canonical kind → DB ref column
    _KIND_TO_REF_FIELD: dict[str, str] = {
        "plan": "plan_ref",
        "run": "report_ref",
        "review": "audit_ref",
    }
    _ACTIVE_KIND_TO_REF_FIELD: dict[str, str] = {
        **_KIND_TO_REF_FIELD,
        "indicate": "indicate_ref",
    }
    # Canonical kind → actor state column
    _KIND_TO_ACTOR_FIELD: dict[str, str] = {
        "plan": "planner_actor",
        "run": "executor_actor",
        "review": "reviewer_actor",
        "indicate": "manager_actor",
    }
    # Legacy kind aliases → canonical kind
    _LEGACY_KIND_ALIASES: dict[str, str] = {
        "report": "run",
        "audit": "review",
    }

    _AUTHORITATIVE_REF_KINDS = {"plan", "report", "audit", "run", "review"}
    _HANDOFF_EVENT_TYPES = {
        "handoff_plan",
        "handoff_report",
        "handoff_run",  # backward-compat: legacy event type
        "handoff_audit",
        "handoff_indicate",
        "next_step_set",
        "plan_recorded",
        "report_recorded",  # new canonical name
        "run_recorded",  # backward-compat: legacy event type
        "audit_recorded",
        "handoff_ci_status",
        "handoff_pr_comment",
    }
    _SUCCESS_HANDOFF_EVENT_TYPES = {
        "handoff_plan",
        "handoff_report",
        "handoff_run",  # backward-compat: legacy name for handoff_report
        "handoff_audit",
        "handoff_indicate",
        "handoff_verdict",
        "handoff_ci_status",
        "handoff_pr_comment",
        "next_step_set",
    }

    @staticmethod
    def _normalize_kind(kind: str) -> str:
        """Normalize kind to canonical form.

        Maps legacy 'report'/'audit' to canonical 'run'/'review',
        lowercases input, and passes through unknown values.
        """
        lowered = kind.lower()
        return HandoffService._LEGACY_KIND_ALIASES.get(lowered, lowered)

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitPathProtocol | None = None,
        github_client: "GitHubClient | None" = None,
    ) -> None:
        """Initialize handoff service.

        Args:
            store: SQLite client for database operations
            git_client: Git client for branch/worktree operations
            github_client: GitHub client for API operations (optional)
        """
        from vibe3.clients import GitHubClient

        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()
        self.storage = HandoffStorage(self.git_client)
        self.external_recorder = ExternalEventRecorder(
            self.store,
            self.storage,
            cast(
                Callable[[str, str | None, int | None], list[FlowEvent]],
                lambda branch, event_type_prefix=None, limit=None: (
                    self.get_handoff_events(  # noqa: E501
                        branch, event_type_prefix, limit
                    )
                ),
            ),
        )

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

    def get_success_handoff_events(
        self,
        branch: str,
        limit: int | None = None,
    ) -> list[FlowEvent]:
        """Return only successful artifact handoff events (plan/report/audit).

        Includes active handoff events (handoff_plan/report/audit) plus
        handoff_indicate (manager) and handoff_verdict (review verdict).

        Args:
            branch: Branch name to query events for.
            limit: Optional limit on number of events to return.

        Returns:
            List of FlowEvent objects representing successful artifact handoffs.
        """
        events_data = self.store.get_events(branch)
        success_events = [
            FlowEvent(**event)
            for event in events_data
            if event["event_type"] in self._SUCCESS_HANDOFF_EVENT_TYPES
        ]
        if limit is not None:
            success_events = success_events[:limit]
        return success_events

    def append_current_handoff(
        self,
        message: str,
        actor: str | None,
        kind: str = "note",
        branch: str | None = None,
        *,
        skip_event: bool = False,
    ) -> Path:
        """Append a lightweight update block to current.md for a branch.

        Args:
            message: Update message
            actor: Actor identifier
            kind: Update kind (note/finding/blocker/next)
            branch: Target branch name (defaults to current branch)
            skip_event: Skip event recording (used internally for dedup)
        """
        target_branch = branch or self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            target_branch,
            explicit_actor=actor,
        )

        # 1. Write to handoff file
        handoff_path = self.storage.append_current_handoff(
            message, effective_actor, kind, target_branch
        )

        # 2. Skip event recording if requested (for dedup)
        if skip_event:
            return handoff_path

        # 3. Record timeline event for milestone handoff updates
        # Query issue_number from branch → issue link
        from vibe3.services.issue.flow import IssueFlowService

        issue_flow_service = IssueFlowService(self.store)
        issue_number = issue_flow_service.resolve_task_issue_number(target_branch)

        # 3. Call FlowTimelineService to record event and optionally write comment
        if issue_number:
            from vibe3.services.flow_timeline_service import FlowTimelineService

            timeline_service = FlowTimelineService(
                store=self.store,
                github_client=self.github_client,
            )

            timeline_service.record_timeline_event(
                branch=target_branch,
                event_type="handoff_append",
                actor=effective_actor,
                detail=message,
                issue_number=issue_number,
            )
        else:
            # No issue_number → only record SQLite event, skip comment
            self.store.add_event(
                target_branch,
                "handoff_append",
                effective_actor,
                detail=message,
            )

        return handoff_path

    def _resolve_branch_worktree_root(self, branch: str) -> Path:
        worktree_root = self.git_client.find_worktree_path_for_branch(branch)
        if worktree_root is not None:
            return worktree_root

        current_root = self.git_client.get_worktree_root()
        if current_root:
            return Path(current_root)

        raise UserError("Cannot validate handoff ref without a worktree root")

    def _record_ref(
        self,
        ref_kind: str,
        ref_value: str,
        actor: str | None = None,
        *,
        verdict: str | None = None,
        branch: str | None = None,
    ) -> Path:
        """Internal helper to record an active handoff reference.

        Args:
            ref_kind: Reference kind (plan/report/audit)
            ref_value: Reference value (path)
            actor: Actor identifier
            verdict: Optional verdict for audit records
            branch: Target branch name (defaults to current branch)

        Note: For passive artifact recording, use record_passive_artifact() instead.
        This method only handles active handoff events (handoff_plan/report/audit).
        """
        target_branch = branch or self.git_client.get_current_branch()
        validate_authoritative_ref(
            ref_kind,
            ref_value,
            target_branch,
            self.git_client,
            self._AUTHORITATIVE_REF_KINDS,
            self._resolve_branch_worktree_root,
        )
        # Inlined _normalize_ref_value
        ref_value = self.storage.normalize_ref_value(ref_value, target_branch)
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            target_branch,
            explicit_actor=actor,
        )

        handoff_path = self.storage.ensure_current_handoff(branch=target_branch)

        # Normalize kind and lookup ref field
        normalized_kind = self._normalize_kind(ref_kind)
        ref_field = self._ACTIVE_KIND_TO_REF_FIELD.get(normalized_kind)
        if not ref_field:
            raise UserError(f"Unsupported handoff kind: {ref_kind}")

        # Build flow state updates
        flow_updates: dict[str, Any] = {ref_field: ref_value}
        actor_field = self._KIND_TO_ACTOR_FIELD.get(normalized_kind)
        if actor_field:
            flow_updates[actor_field] = effective_actor

        # NOTE: blocked_reason management is handled by BlockedStateService.
        # Handoff service does NOT clear blocked_reason automatically because:
        # 1. ERROR and BLOCK systems are now separated (PR #1366)
        # 2. blocked_reason is managed by BlockedStateService for consistency
        # 3. User-set blocked_reason should only be cleared via unblock command
        # 4. No transient blocked_reason patterns exist in current architecture

        if verdict:
            role = extract_role_from_actor(effective_actor)
            record = VerdictRecord(
                verdict=verdict,  # type: ignore
                actor=effective_actor,
                role=role,
                timestamp=datetime.now(UTC),
                reason=f"Recorded {ref_kind} reference",
                issues=None,
                flow_branch=target_branch,
            )
            flow_updates["latest_verdict"] = record.model_dump_json()

        message = f"Recorded {ref_kind} reference: {ref_value}"
        if verdict:
            message = f"verdict: {verdict}\n{message}"

        self.store.update_flow_state(target_branch, **flow_updates)

        event_refs: dict[str, str] = {ref_field: ref_value}
        if verdict:
            event_refs["verdict"] = verdict

        # Active handoff event type (passive recorded via record_passive_artifact)
        event_type = f"handoff_{ref_kind.lower()}"
        self.store.add_event(
            target_branch,
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
                branch=target_branch,
                skip_event=True,
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
        actor: str | None = None,
        branch: str | None = None,
    ) -> Path:
        """Record plan handoff reference.

        Args:
            plan_ref: Plan document reference
            actor: Actor identifier
            branch: Target branch name (defaults to current branch)
        """
        return self._record_ref("plan", plan_ref, actor, branch=branch)

    def record_report(
        self,
        report_ref: str,
        actor: str | None = None,
        branch: str | None = None,
    ) -> Path:
        """Record report handoff reference.

        Args:
            report_ref: Report document reference
            actor: Actor identifier
            branch: Target branch name (defaults to current branch)
        """
        return self._record_ref("report", report_ref, actor, branch=branch)

    def record_audit(
        self,
        audit_ref: str,
        actor: str | None = None,
        verdict: str | None = None,
        is_system_auto: bool = False,
        branch: str | None = None,
    ) -> Path:
        """Record audit handoff reference.

        Args:
            audit_ref: Audit document reference
            actor: Actor identifier
            verdict: Optional verdict value
            is_system_auto: If True, creates passive artifact
            branch: Target branch name (defaults to current branch)

        If is_system_auto=True, creates a passive artifact via record_passive_artifact.
        Otherwise, creates an active handoff event.
        """
        if is_system_auto:
            # Use passive artifact recording for system auto-generated audits
            result = self.record_passive_artifact(
                kind="audit",
                content=audit_ref,
                actor=actor,
                branch=branch,
                verdict=verdict,
            )
            # record_passive_artifact returns Path or None, but this method
            # always returns Path
            # If None (empty content), still return the handoff path
            if result is None:
                # Fallback: return current handoff path
                return self.storage.ensure_current_handoff(branch=branch)
            return result
        else:
            # Active handoff recording
            return self._record_ref(
                "audit",
                audit_ref,
                actor,
                verdict=verdict,
                branch=branch,
            )

    def record_indicate(
        self,
        indicate_ref: str,
        actor: str | None = None,
        branch: str | None = None,
    ) -> Path:
        """Record manager indicate handoff reference.

        Args:
            indicate_ref: Manager indicate document reference
            actor: Actor identifier
            branch: Target branch name (defaults to current branch)
        """
        return self._record_ref("indicate", indicate_ref, actor, branch=branch)

    def record_next_step(
        self,
        branch: str,
        next_step: str,
        actor: str | None = None,
    ) -> None:
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )
        self.store.update_flow_state(
            branch,
            next_step=next_step,
            latest_actor=effective_actor,
        )
        self.store.add_event(
            branch,
            "next_step_set",
            effective_actor,
            detail=f"Next Step: {next_step}",
        )

    def record_passive_artifact(
        self,
        *,
        kind: str,
        content: str,
        actor: str | None = None,
        metadata: dict[str, str] | None = None,
        branch: str | None = None,
        # Audit-specific optional parameters
        verdict: str | None = None,
        next_step: str | None = None,
        blocked_by: str | None = None,
    ) -> Path | None:
        """Record a shared fallback artifact without upgrading authoritative refs.

        Supports all three artifact kinds: plan, report, audit.
        Audit can optionally include verdict, next_step, blocked_by.

        Args:
            kind: Artifact kind ("plan", "report", or "audit")
            content: Artifact content
            actor: Actor string (resolved from signature service if None)
            metadata: Optional metadata dict
            branch: Target branch (current if None)
            verdict: Optional verdict value (audit only)
            next_step: Optional next step (audit only)
            blocked_by: Optional blocked by description (audit only)

        Returns:
            Path to created artifact, or None if content is empty

        Raises:
            UserError: If kind is not supported
        """
        # Normalize kind and validate
        normalized_kind = self._normalize_kind(kind)
        if normalized_kind not in self._KIND_TO_REF_FIELD:
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

        # Use legacy prefix for artifact creation (backward compat)
        artifact_prefix = {"plan": "plan", "run": "report", "review": "audit"}.get(
            normalized_kind, normalized_kind
        )
        created = self.storage.create_artifact(
            prefix=artifact_prefix,
            content=sanitized_content + "\n",
            branch=target_branch,
        )
        if created is None:
            return None
        _, artifact_path = created

        # Use normalized kind for artifact detail
        detail, extra_refs = ArtifactParser.build_artifact_detail(
            normalized_kind,
            sanitized_content,
            artifact_path,
            metadata=metadata,
        )

        # Build event_type (use "report_recorded" for run kind)
        event_type = (
            "report_recorded"
            if normalized_kind == "run"
            else f"{artifact_prefix}_recorded"
        )

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

        # Build refs with the same database ref field used by flow_state.
        ref_field = self._KIND_TO_REF_FIELD[normalized_kind]
        refs: dict[str, str | list[str]] = {ref_field: ref_value}
        refs.update(extra_refs)

        # Add audit-specific refs if provided
        if kind == "audit":
            if verdict:
                refs["verdict"] = verdict
            # Add verdict and other fields to detail for audit
            detail_parts = [detail]
            if verdict:
                detail_parts.insert(0, f"verdict: {verdict}")
            if next_step:
                detail_parts.append(f"Next Step: {next_step}")
            if blocked_by:
                detail_parts.append(f"Blocked By: {blocked_by}")
            detail = "\n".join(detail_parts)

        self.store.add_event(
            target_branch,
            event_type,
            effective_actor,
            detail=detail,
            refs=refs,
        )
        return artifact_path

    def record_ci_status(
        self,
        branch: str,
        pr_number: int,
        status: str,
        actor: str = "system/github",
    ) -> bool:
        """Record CI status as external event.

        Only records if status changed from last recorded status.

        Args:
            branch: Branch name
            pr_number: PR number
            status: CI status string (e.g., "SUCCESS", "FAILURE", "PENDING")
            actor: Actor string (defaults to "system/github")

        Returns:
            True if event was recorded, False if skipped (no change)
        """
        return self.external_recorder.record_ci_status(branch, pr_number, status, actor)

    def record_pr_comments(
        self,
        branch: str,
        pr_number: int,
        comments: list[dict[str, Any]],
        review_comments: list[dict[str, Any]] | None = None,
        actor: str = "system/github",
    ) -> int:
        """Record PR comments as external events.

        Only records comments not already recorded (dedup by comment ID).

        Args:
            branch: Branch name
            pr_number: PR number
            comments: List of general comments (each has 'id' or 'number' field)
            review_comments: List of review comments (each has 'id' field)
            actor: Actor string (defaults to "system/github")

        Returns:
            Number of new comments recorded
        """
        return self.external_recorder.record_pr_comments(
            branch, pr_number, comments, review_comments, actor
        )
