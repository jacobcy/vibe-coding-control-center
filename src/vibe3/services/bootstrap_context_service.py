from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BootstrapActionKind = Literal[
    "ensure_branch",
    "flow_update",
    "flow_bind_task",
    "snapshot_baseline",
    "pr_create_optional",
    "handoff_append",
    "create_worktree",
]


@dataclass(frozen=True)
class BootstrapAction:
    kind: BootstrapActionKind
    command: str
    reason: str


@dataclass(frozen=True)
class BootstrapPlan:
    target_branch: str
    issue_number: int
    requires_worktree: bool = False
    actions: list[BootstrapAction] = field(default_factory=list)


class BootstrapContextService:
    """Plan vibe-new bootstrap actions.

    This service outputs action plans for skill layer orchestration.
    It does NOT execute commands directly.
    """

    def plan_vibe_new_bootstrap(
        self,
        *,
        current_branch: str,
        target_branch: str,
        issue_number: int,
        has_existing_flow: bool,
        has_existing_pr: bool,
        wants_worktree: bool,
    ) -> BootstrapPlan:
        """Plan atomic bootstrap actions for vibe-new entry.

        Args:
            current_branch: Current git branch
            target_branch: Target branch (dev/issue-XXX)
            issue_number: GitHub issue number
            has_existing_flow: Whether flow already exists
            has_existing_pr: Whether PR already exists
            wants_worktree: Whether user wants new worktree

        Returns:
            BootstrapPlan with ordered actions
        """
        actions: list[BootstrapAction] = []

        # Step 1: Ensure branch (if needed)
        if current_branch != target_branch:
            actions.append(
                BootstrapAction(
                    kind="ensure_branch",
                    command=f"git checkout -b {target_branch}",
                    reason="Create or switch to human-collaboration branch.",
                )
            )

        # Step 2: Create worktree (if requested)
        if wants_worktree:
            actions.append(
                BootstrapAction(
                    kind="create_worktree",
                    command=f"wtnew {target_branch}",
                    reason="Create isolated worktree for parallel development.",
                )
            )

        # Step 3: Register flow (idempotent)
        if not has_existing_flow:
            actions.append(
                BootstrapAction(
                    kind="flow_update",
                    command="vibe3 flow update --actor <identity>",
                    reason="Register current branch as flow scene.",
                )
            )

        # Step 4: Bind task issue
        actions.append(
            BootstrapAction(
                kind="flow_bind_task",
                command=f"vibe3 flow bind {issue_number} --role task",
                reason="Bind the task issue to current flow.",
            )
        )

        # Step 5: Save baseline
        actions.append(
            BootstrapAction(
                kind="snapshot_baseline",
                command="vibe3 snapshot save --as-baseline",
                reason="Persist a branch baseline for later structural diff.",
            )
        )

        # Step 6: Create PR draft (optional)
        if not has_existing_pr:
            actions.append(
                BootstrapAction(
                    kind="pr_create_optional",
                    command='vibe3 pr create --agent -t "..." -b "..."',
                    reason="Create PR draft if branch has commits.",
                )
            )

        # Step 7: Record handoff
        actions.append(
            BootstrapAction(
                kind="handoff_append",
                command=(
                    'vibe3 handoff append "vibe-new: flow ready" '
                    "--actor vibe-new --kind milestone"
                ),
                reason="Record a stable resume point after bootstrap.",
            )
        )

        return BootstrapPlan(
            target_branch=target_branch,
            issue_number=issue_number,
            requires_worktree=wants_worktree,
            actions=actions,
        )
