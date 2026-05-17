from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Literal

BootstrapActionKind = Literal[
    "bootstrap_flow_scene",
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
    """Plan vibe-new bootstrap actions.

    This service outputs action plans for skill layer orchestration.
    It does NOT execute commands directly.
    """

    def plan_vibe_new_bootstrap(
        self,
        *,
        target_branch: str,
        issue_number: int,
        has_existing_pr: bool,
        wants_worktree: bool,
        related_issue_numbers: tuple[int, ...] = (),
        dependency_issue_numbers: tuple[int, ...] = (),
    ) -> BootstrapPlan:
        """Plan shared bootstrap actions for vibe-new entry.

        Args:
            target_branch: Target branch (dev/issue-XXX)
            issue_number: GitHub issue number
            has_existing_pr: Whether PR already exists
            wants_worktree: Whether user wants new worktree
            related_issue_numbers: Optional related issue bindings
            dependency_issue_numbers: Optional dependency issue bindings

        Returns:
            BootstrapPlan with ordered actions
        """
        actions: list[BootstrapAction] = []
        related_flags = " ".join(
            f"--related {shlex.quote(str(issue_ref))}"
            for issue_ref in related_issue_numbers
        )
        dependency_flags = " ".join(
            f"--dependency {shlex.quote(str(issue_ref))}"
            for issue_ref in dependency_issue_numbers
        )
        worktree_flag = "--worktree" if wants_worktree else ""
        extra_flags = " ".join(
            flag
            for flag in (worktree_flag, related_flags, dependency_flags)
            if flag.strip()
        )
        command = (
            f"vibe3 internal bootstrap-flow {shlex.quote(str(issue_number))} "
            f"--branch {shlex.quote(target_branch)} --source skill"
        )
        if extra_flags:
            command = f"{command} {extra_flags}"

        actions.append(
            BootstrapAction(
                kind="bootstrap_flow_scene",
                command=command,
                reason=(
                    "Use the shared internal bootstrap entry so skill and "
                    "orchestra reach the same standardized flow scene path."
                ),
            )
        )

        if not has_existing_pr:
            actions.append(
                BootstrapAction(
                    kind="pr_create_optional",
                    command='vibe3 pr create --agent -t "..." -b "..."',
                    reason="Create PR draft if branch has commits.",
                )
            )

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
