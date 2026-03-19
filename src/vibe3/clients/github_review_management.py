"""GitHub review management operations."""

import json
import subprocess
from typing import Any

from loguru import logger


class ReviewManagementMixin:
    """Mixin for review management operations."""

    def list_reviews(self: Any, pr_number: int) -> list[dict[str, Any]]:
        """List all reviews on a PR.

        Args:
            pr_number: PR 编号

        Returns:
            List of review dicts
        """
        logger.bind(
            external="github",
            operation="list_reviews",
            pr_number=pr_number,
        ).debug("Calling GitHub API: list_reviews")
        result = subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def dismiss_review(self: Any, pr_number: int, review_id: int, message: str) -> None:
        """Dismiss a review.

        Args:
            pr_number: PR 编号
            review_id: Review ID
            message: Dismissal message
        """
        logger.bind(
            external="github",
            operation="dismiss_review",
            pr_number=pr_number,
            review_id=review_id,
        ).debug("Calling GitHub API: dismiss_review")
        subprocess.run(
            [
                "gh",
                "api",
                f"/repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews/{review_id}/dismissals",
                "--method",
                "PUT",
                "--field",
                f"message={message}",
            ],
            check=True,
        )

    def dismiss_bot_reviews(
        self: Any, pr_number: int, bot_name: str = "github-actions[bot]"
    ) -> None:
        """Dismiss all pending reviews from a bot.

        Args:
            pr_number: PR 编号
            bot_name: Bot user name to filter
        """
        log = logger.bind(
            external="github",
            operation="dismiss_bot_reviews",
            pr_number=pr_number,
            bot_name=bot_name,
        )
        log.debug("Checking for existing bot reviews")
        reviews = self.list_reviews(pr_number)
        bot_reviews = [
            r
            for r in reviews
            if r.get("user", {}).get("login") == bot_name
            and r.get("state") == "PENDING"
        ]
        if bot_reviews:
            log.bind(count=len(bot_reviews)).info("Dismissing existing bot reviews")
            for review in bot_reviews:
                self.dismiss_review(
                    pr_number,
                    review["id"],
                    "Dismissing outdated review - new review in progress",
                )
        else:
            log.debug("No pending bot reviews found")
