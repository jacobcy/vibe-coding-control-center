"""Service for publishing an evidence-only PR reviewer briefing."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibe3.analysis import build_review_observation
from vibe3.clients import GitClient, GitHubClientProtocol
from vibe3.models import ReviewObservation

SENTINEL = "<!-- vibe3:pr-review-briefing -->"


class PRReviewBriefingService:
    """Publish a singleton briefing backed by exact local review evidence."""

    def __init__(self, github_client: GitHubClientProtocol) -> None:
        self.github_client = github_client

    def publish_briefing(
        self, pr_number: int, requested_reviewers: list[str] | None = None
    ) -> str:
        pr_details = self.github_client.get_pr(pr_number)
        observation = self._load_observation(pr_details)
        body = self._render_briefing(
            pr_number,
            pr_details,
            observation,
            requested_reviewers,
        )

        existing_comment = self._find_briefing_comment(pr_number)
        if existing_comment:
            return self.github_client.update_pr_comment(
                str(existing_comment["id"]), body
            )
        return self.github_client.create_pr_comment(pr_number, body)

    def _load_observation(self, pr_details: Any) -> ReviewObservation | None:
        """Return evidence only when the PR head is the active worktree."""
        try:
            if pr_details is None:
                return None
            git = GitClient()
            if git.get_current_branch() != pr_details.head_branch:
                return None
            repo_root = Path(git.get_worktree_root())
            result = build_review_observation(
                requested_base=pr_details.base_branch,
                resolved_base=pr_details.base_branch,
                git=git,
                manifest_path=repo_root / "config" / "v3" / "review_kernel.yaml",
            )
            return None if result.status == "error" else result
        except Exception:
            return None

    def _find_briefing_comment(self, pr_number: int) -> dict[str, Any] | None:
        for comment in self.github_client.list_pr_comments(pr_number):
            if SENTINEL in comment.get("body", ""):
                return comment
        return None

    def _render_briefing(
        self,
        pr_number: int,
        pr_details: Any,
        observation: ReviewObservation | None,
        requested_reviewers: list[str] | None = None,
    ) -> str:
        """Render Git facts and Review Kernel policy without impact claims."""
        lines = [f"## Reviewer Briefing {SENTINEL}", ""]

        if pr_details:
            route = f"`{pr_details.base_branch}` ← `{pr_details.head_branch}`"
            lines.extend(
                ["### Context", f"- **PR:** #{pr_number}", f"- **Route:** {route}"]
            )
            if pr_details.metadata and pr_details.metadata.task_issue:
                lines.append(f"- **Linked Issue:** #{pr_details.metadata.task_issue}")
            lines.append("")

        if observation is None:
            lines.extend(
                [
                    "### Review Observation",
                    "- Exact local observation unavailable for this PR head.",
                    "- Runtime impact analysis: disabled.",
                    "",
                    "### Please focus on",
                    "1. Review the GitHub diff directly.",
                    "",
                ]
            )
        else:
            summary = observation.changes.summary
            lines.extend(
                [
                    "### Review Observation",
                    f"- **Status:** `{observation.status}`",
                    f"- **Committed files:** {summary.committed.files}",
                    f"- **Staged files:** {summary.staged.files}",
                    f"- **Unstaged files:** {summary.unstaged.files}",
                    "- **Runtime impact analysis:** disabled",
                ]
            )
            if observation.kernel is not None:
                lines.append(
                    f"- **Kernel impact:** `{observation.kernel.impact.value}`"
                )
                hits = (
                    observation.kernel.architecture_hits
                    + observation.kernel.review_hits
                )
                if hits:
                    lines.append("- **Kernel files:**")
                    lines.extend(f"  - `{hit.path}`" for hit in hits)
            if observation.review is not None:
                lines.append(
                    "- **Minimum review depth:** "
                    f"`{observation.review.minimum_depth.value}`"
                )
            lines.extend(["", "### Please focus on"])
            depth = (
                observation.review.minimum_depth.value
                if observation.review is not None
                else "normal"
            )
            lines.append(f"1. Apply at least `{depth}` review depth.")
            lines.append("2. Verify the exact changed files shown by Git.")
            lines.append("")

        if requested_reviewers:
            lines.extend(
                [
                    "## Requested AI Review",
                    f"Reviewers: {', '.join(requested_reviewers)}",
                    "Requested at: "
                    + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    "",
                ]
            )

        lines.extend(["---", "*Generated by vibe3 pr ready*"])
        return "\n".join(lines)
