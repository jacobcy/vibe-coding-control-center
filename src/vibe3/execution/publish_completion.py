"""Completion boundary for a publish execution that creates a new PR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from vibe3.models import IssueState, PRResponse


class PublishPRReader(Protocol):
    def list_prs_for_branch(
        self, branch: str, *, state: str | None = None, repo: str | None = None
    ) -> list[PRResponse]: ...


class PublishLabelWriter(Protocol):
    def confirm_issue_state(
        self,
        issue_number: int,
        to_state: IssueState,
        actor: str,
        force: bool = False,
    ) -> Literal["confirmed", "advanced", "blocked"]: ...


class PublishTransitionRecorder(Protocol):
    def would_exceed(self, branch: str, from_state: str, to_state: str) -> bool: ...

    def record_confirmed(
        self,
        *,
        branch: str,
        from_state: str,
        to_state: str,
        actor: str,
        issue_number: int,
    ) -> object: ...


@dataclass(frozen=True)
class PublishCompletionResult:
    completed: bool
    pr_number: int | None = None
    reason: str = ""


class PublishCompletionService:
    """Apply the one normal transition explicitly owned by code."""

    def __init__(
        self,
        github: PublishPRReader,
        labels: PublishLabelWriter,
        recorder: PublishTransitionRecorder,
    ) -> None:
        self._github = github
        self._labels = labels
        self._recorder = recorder

    def try_complete(
        self,
        *,
        issue_number: int,
        branch: str,
        before_state_labels: frozenset[str],
        before_open_pr_numbers: frozenset[int],
        actor: str,
    ) -> PublishCompletionResult:
        if before_state_labels != frozenset({"state/merge-ready"}):
            return PublishCompletionResult(
                False,
                reason="publish did not start in state/merge-ready",
            )
        if before_open_pr_numbers:
            return PublishCompletionResult(
                False,
                reason="an open PR existed before publish",
            )

        after_prs = self._github.list_prs_for_branch(branch, state="open")
        new_numbers = {
            pr.number for pr in after_prs if pr.number not in before_open_pr_numbers
        }
        if len(new_numbers) != 1:
            return PublishCompletionResult(
                False,
                reason="publish did not create exactly one open PR",
            )

        from_state = "state/merge-ready"
        to_state = "state/handoff"
        if self._recorder.would_exceed(branch, from_state, to_state):
            return PublishCompletionResult(
                False,
                reason="publish transition limit reached",
            )

        write_result = self._labels.confirm_issue_state(
            issue_number,
            IssueState.HANDOFF,
            actor=actor,
            force=False,
        )
        if write_result != "advanced":
            return PublishCompletionResult(
                False,
                reason=f"handoff transition not applied: {write_result}",
            )

        pr_number = next(iter(new_numbers))
        self._recorder.record_confirmed(
            branch=branch,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            issue_number=issue_number,
        )
        return PublishCompletionResult(True, pr_number=pr_number)
