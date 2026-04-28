"""Flow write operations mixin.

Inherits from FlowReadMixin to access get_flow_status method.
"""

from typing import Self

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import FlowStatusResponse, MainBranchProtectedError
from vibe3.services.flow_read_mixin import FlowReadMixin
from vibe3.services.signature_service import SignatureService


class FlowWriteMixin(FlowReadMixin):
    """Mixin providing flow write operations.

    Inherits FlowReadMixin for:
    - get_flow_status (flow status query)
    """

    store: SQLiteClient
    config: VibeConfig

    def _is_main_branch(self: Self, branch: str) -> bool:
        """Check if branch is a protected main branch.

        Protected branches include:
        - Configured protected_branches (e.g. main, master, develop)
        - Remote tracking variants (origin/main, etc.)
        - Safe branches created by flow close (vibe/main-safe/...)
        """
        # Strip remote prefix for safe branch check (origin/vibe/main-safe/...)
        local_name = branch.split("/", 1)[1] if branch.startswith("origin/") else branch
        if local_name.startswith(FlowWriteMixin.SAFE_BRANCH_PREFIX):
            return True

        # Check against configured protected branches
        protected = self.config.flow.protected_branches

        # Direct match
        if branch in protected:
            return True

        # Check for remote tracking branches (origin/main, etc.)
        for protected_branch in protected:
            if branch == f"origin/{protected_branch}":
                return True

        return False

    SAFE_BRANCH_PREFIX = "vibe/main-safe/"

    def create_flow(
        self: Self,
        slug: str,
        branch: str,
        actor: str | None = None,
        initiated_by: str | None = None,
        *,
        source: str = "unknown",
    ) -> FlowStatusResponse:
        """Create a new flow.

        Args:
            slug: Flow name/slug
            branch: Git branch name
            actor: Optional actor name
            initiated_by: Optional initiator identifier
            source: Caller identity for audit logging
                (e.g. "dispatch", "cli", "agent").

        Returns:
            Created flow state

        Raises:
            MainBranchProtectedError: If branch is main/master
        """
        if self._is_main_branch(branch):
            raise MainBranchProtectedError(
                f"Cannot create flow on protected branch '{branch}'. "
                "Switch to a feature branch first."
            )

        # Idempotency: if flow already exists, return existing
        existing_state = self.store.get_flow_state(branch)
        if existing_state:
            existing_slug = existing_state.get("flow_slug", slug)
            logger.bind(
                domain="flow",
                action="create",
                branch=branch,
                source=source,
                existing_slug=existing_slug,
            ).warning(
                f"Flow already exists for '{branch}' "
                f"(slug={existing_slug}, source={source}). "
                f"Returning existing — use reactivate_flow to reset."
            )
            existing = self.get_flow_status(branch)
            if existing is not None:
                return existing
            # get_flow_state found a row but get_flow_status returned None;
            # fall through to recreate (should not happen in practice).

        logger.bind(
            domain="flow",
            action="create",
            slug=slug,
            branch=branch,
            initiated_by=initiated_by,
            source=source,
        ).info("Creating flow")
        # Flow state actor: only set when explicitly provided.
        # orchestra uses actor=None to signal "no agent has taken ownership yet".
        effective_actor = (
            SignatureService.resolve_actor(explicit_actor=actor)
            if actor is not None
            else None
        )
        # Event actor: audit log always needs attribution (NOT NULL in schema).
        # Falls back to worktree identity when no explicit actor — this is an
        # audit record, not an agent claim, so the distinction is fine.
        event_actor = effective_actor or SignatureService.get_worktree_actor()

        # Resolve initiator if not explicitly provided (e.g. manual CLI create)
        if initiated_by is None:
            initiated_by = SignatureService.resolve_initiator(branch)

        self.store.update_flow_state(
            branch,
            flow_slug=slug,
            latest_actor=effective_actor,
            initiated_by=initiated_by,
        )

        self.store.add_event(
            branch,
            "flow_created",
            event_actor,
            f"Flow '{slug}' created",
            refs={"source": source},
        )

        status = self.get_flow_status(branch)
        if not status:
            raise RuntimeError(f"Failed to create flow for branch {branch}")

        return status

    def update_flow_metadata(self: Self, branch: str, **updates: object) -> None:
        """Update flow metadata fields (slug, actor, etc.).

        Encapsulates store.update_flow_state so commands don't need
        direct store access.

        Args:
            branch: Flow branch name
            **updates: Keyword args passed to store.update_flow_state
        """
        self.store.update_flow_state(branch, **updates)

    def delete_flow(self: Self, branch: str, force: bool = False) -> None:
        """Delete all persisted flow truth for a branch.

        This is the hard-reset counterpart to ``reactivate_flow()``.
        It removes authoritative database state so any future manager/planner
        pass must recreate the flow scene from scratch instead of inheriting
        stale refs, events, issue links, or runtime session registry entries.

        Args:
            branch: Branch name
            force: If True, hard delete (physical removal); otherwise soft delete
        """
        action = "hard deleting" if force else "soft deleting"
        logger.bind(
            domain="flow",
            action="delete",
            branch=branch,
            force=force,
        ).info(f"{action.capitalize()} flow")
        self.store.delete_flow(branch, force=force)

    def bind_spec(
        self: Self,
        branch: str,
        spec_ref: str,
        actor: str | None = None,
    ) -> None:
        """Bind a spec to a flow.

        Args:
            branch: Branch name
            spec_ref: Spec file reference
            actor: Actor performing the bind
        """
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )
        self.store.update_flow_state(
            branch, spec_ref=spec_ref, latest_actor=effective_actor
        )
        self.store.add_event(
            branch, "spec_bound", effective_actor, detail=f"Spec bound: {spec_ref}"
        )
        logger.bind(branch=branch, spec=spec_ref).info("Spec bound to flow")
