"""Dependency closure gate.

Posts advisory comments on downstream issues when an upstream dependency closes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient


class DependencyClosureGate:
    """Gate that notifies downstream flows when an upstream dependency closes."""

    @staticmethod
    def notify_downstream(
        *,
        issue_number: int,
        store: SQLiteClient,
        github_client: GitHubClient,
    ) -> list[int]:
        """Post advisory comments on downstream issues.

        Args:
            issue_number: The closed upstream issue number.
            store: SQLite client for flow state queries.
            github_client: GitHub client for posting comments.

        Returns:
            List of downstream issue numbers that were notified.
        """
        branches = store.get_issue_dependents(issue_number)

        if not branches:
            logger.bind(
                domain="dispatch",
                action="dependency_closure_gate",
                issue_number=issue_number,
            ).debug("No dependents found; skipping advisory")
            return []

        notified: list[int] = []

        for branch in branches:
            # Resolve task issue number for this dependent branch
            dependent_issue_number = store.get_task_issue_number(branch)
            if dependent_issue_number is None:
                logger.bind(
                    domain="dispatch",
                    action="dependency_closure_gate",
                    branch=branch,
                    upstream_issue=issue_number,
                ).debug("Branch has no task issue; skipping")
                continue

            # Post advisory comment (add_comment will fail if issue is closed)
            comment_body = (
                f"[dispatch] Advisory: upstream dependency #{issue_number} "
                "of this issue was just closed.\n"
                "If its scope was not delivered, this flow may remain "
                "permanently blocked.\n"
                "Please verify or update the dependency contract "
                "(see audit issue #3229)."
            )

            try:
                github_client.add_comment(dependent_issue_number, comment_body)
                notified.append(dependent_issue_number)
                logger.bind(
                    domain="dispatch",
                    action="dependency_closure_gate",
                    issue_number=dependent_issue_number,
                    upstream_issue=issue_number,
                ).info("Posted dependency closure advisory")
            except Exception as exc:
                # Log but don't block - advisory comments are non-critical
                logger.bind(
                    domain="dispatch",
                    action="dependency_closure_gate",
                    issue_number=dependent_issue_number,
                    upstream_issue=issue_number,
                    error=str(exc),
                ).warning(f"Failed to post advisory comment: {exc}")

        logger.bind(
            domain="dispatch",
            action="dependency_closure_gate",
            issue_number=issue_number,
            notified_count=len(notified),
        ).info("Dependency closure gate complete")

        return notified
