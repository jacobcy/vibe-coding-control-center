from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

BootstrapActionKind = Literal[
    "resolve_worktree_context",
    "git_checkout_branch",
    "flow_update",
    "flow_bind_task",
    "snapshot_baseline",
    "pr_create_optional",
    "handoff_append",
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
        actions: list[BootstrapAction] = []

        if wants_worktree:
            actions.append(
                BootstrapAction(
                    kind="resolve_worktree_context",
                    command="python:environment.resolve_bootstrap_worktree(...)",
                    reason=(
                        "Prepare physical worktree/session context before flow updates."
                    ),
                )
            )

        if current_branch != target_branch:
            actions.append(
                BootstrapAction(
                    kind="git_checkout_branch",
                    command=f"git checkout -b {target_branch}",
                    reason="Create or switch to the human-collaboration branch.",
                )
            )

        if not has_existing_flow:
            actions.append(
                BootstrapAction(
                    kind="flow_update",
                    command="vibe3 flow update --actor <identity>",
                    reason="Register current branch as a flow scene.",
                )
            )

        actions.append(
            BootstrapAction(
                kind="flow_bind_task",
                command=f"vibe3 flow bind {issue_number} --role task",
                reason="Bind the task issue to the current flow.",
            )
        )
        actions.append(
            BootstrapAction(
                kind="snapshot_baseline",
                command="vibe3 snapshot save --as-baseline",
                reason="Persist a branch baseline for later structural diff.",
            )
        )
        if not has_existing_pr:
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
