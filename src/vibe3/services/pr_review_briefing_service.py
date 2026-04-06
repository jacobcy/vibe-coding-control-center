"""Service for generating and publishing PR reviewer briefing comments."""

from datetime import datetime, timezone
from typing import Any

from vibe3.clients.protocols import GitHubClientProtocol

SENTINEL = "<!-- vibe3:pr-review-briefing -->"


class PRReviewBriefingService:
    """Service to handle PR reviewer briefing logic."""

    def __init__(self, github_client: GitHubClientProtocol) -> None:
        self.github_client = github_client

    def publish_briefing(
        self, pr_number: int, requested_reviewers: list[str] | None = None
    ) -> str:
        """
        Generate and publish/update the briefing comment on a PR.

        Args:
            pr_number: PR number
            requested_reviewers: List of AI reviewers (e.g., ['codex', 'copilot'])

        Returns:
            Comment URL or ID
        """
        from vibe3.services.pr_analysis_service import build_pr_analysis

        analysis = build_pr_analysis(pr_number)
        body = self._render_briefing(analysis, requested_reviewers)

        # Sentinel is the singleton key. Update any existing briefing.
        existing_comment = self._find_briefing_comment(pr_number)
        if existing_comment:
            comment_id = str(existing_comment["id"])
            return self.github_client.update_pr_comment(comment_id, body)
        else:
            return self.github_client.create_pr_comment(pr_number, body)

    def _find_briefing_comment(self, pr_number: int) -> dict[str, Any] | None:
        """Find existing briefing comment by sentinel (singleton for PR)."""
        comments = self.github_client.list_pr_comments(pr_number)
        for comment in comments:
            body = comment.get("body", "")
            if SENTINEL in body:
                return comment
        return None

    def _render_briefing(
        self, analysis: Any, requested_reviewers: list[str] | None = None
    ) -> str:
        """Render briefing markdown body with optional AI review section."""
        # Get PR details for better context if available
        pr_details = self.github_client.get_pr(analysis.pr_number)

        score_data = analysis.score.get("score", {})
        if isinstance(score_data, (int, float)):
            score = score_data
            level = str(analysis.score.get("level", "UNKNOWN")).split(".")[-1]
            reason = analysis.score.get("reason", "")
        else:
            score = score_data.get("score", "N/A")
            level = str(score_data.get("level", "UNKNOWN")).split(".")[-1]
            reason = score_data.get("reason", "")

        lines = [
            f"## Reviewer Briefing {SENTINEL}",
            "",
            f"**Risk Profile:** `{level}` (Score: {score})",
            f"> {reason}" if reason else "",
            "",
        ]

        if pr_details:
            route = f"`{pr_details.base_branch}` ← `{pr_details.head_branch}`"
            lines.extend(
                [
                    "### Context",
                    f"- **Route:** {route}",
                ]
            )
            # Best-effort task issue link
            if pr_details.metadata and pr_details.metadata.task_issue:
                lines.append(f"- **Linked Issue:** #{pr_details.metadata.task_issue}")
            lines.append("")

        lines.extend(
            [
                "### Change Summary",
                f"- **Files Changed:** {analysis.total_files}",
                f"- **Commits:** {analysis.total_commits}",
                "",
            ]
        )

        if analysis.critical_files:
            lines.append("### Critical Files Touched")
            for f in analysis.critical_files:
                marker = " [API]" if f.get("public_api") else ""
                lines.append(f"- `{f['path']}`{marker}")
            lines.append("")

        if analysis.critical_symbols:
            lines.append("### Changed Symbols (Critical)")
            for file, symbols in analysis.critical_symbols.items():
                sym_list = ", ".join([f"`{s}`" for s in symbols])
                lines.append(f"- `{file}`: {sym_list}")
            lines.append("")

        if analysis.impacted_modules:
            lines.append("### Impacted Modules (DAG)")
            modules = ", ".join([f"`{m}`" for m in analysis.impacted_modules[:10]])
            if len(analysis.impacted_modules) > 10:
                modules += " ..."
            lines.append(modules)
            lines.append("")

        # Add "Please focus on" section
        lines.append("### Please focus on")
        if analysis.critical_files:
            lines.append("1. **Critical Logic**: Review core/API changes listed above.")
        if analysis.impacted_modules:
            count = len(analysis.impacted_modules)
            lines.append(f"2. **Impact Radius**: Verify effects on {count} modules.")
        if not analysis.critical_files and not analysis.impacted_modules:
            lines.append("1. Standard review of non-critical changes.")
        lines.append("")

        # Add AI review request section if reviewers specified
        if requested_reviewers:
            lines.append("## 🤖 Requested AI Review")
            reviewers_str = ", ".join(requested_reviewers)
            lines.append(f"Reviewers: {reviewers_str}")
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"Requested at: {timestamp}")
            lines.append("")

        lines.append("---")
        lines.append("*Generated by vibe3 pr ready*")

        return "\n".join(lines)
