"""Review service implementation."""

import subprocess

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.protocols import GitHubClientProtocol
from vibe3.models.pr import PRResponse, ReviewResponse


class ReviewService:
    """Service for PR review using local LLM."""

    def __init__(self, github_client: GitHubClientProtocol | None = None) -> None:
        """Initialize review service.

        Args:
            github_client: GitHub client for API operations
        """
        self.github_client = github_client or GitHubClient()

    def review_pr(
        self,
        pr_number: int,
        publish: bool = True,
    ) -> ReviewResponse:
        """Review PR using local LLM (codex).

        Args:
            pr_number: PR number
            publish: Whether to publish review as comment

        Returns:
            Review response

        Raises:
            RuntimeError: If PR not found or codex unavailable
        """
        logger.info("Reviewing PR", pr_number=pr_number, publish=publish)

        # Get PR details
        pr = self.github_client.get_pr(pr_number)
        if not pr:
            raise RuntimeError(f"PR #{pr_number} not found")

        # Get PR diff
        diff = self.github_client.get_pr_diff(pr_number)

        # Build review prompt
        prompt = self._build_review_prompt(pr, diff)

        # Run codex review
        review_body = self._run_codex_review(prompt)

        # Publish review if requested
        published = False
        if publish:
            self.github_client.add_pr_comment(pr_number, review_body)
            published = True
            logger.info("Review published to PR", pr_number=pr_number)

        return ReviewResponse(
            pr_number=pr_number,
            review_body=review_body,
            published=published,
        )

    def _build_review_prompt(self, pr: PRResponse, diff: str) -> str:
        """Build review prompt for codex.

        Args:
            pr: PR details
            diff: PR diff

        Returns:
            Review prompt
        """
        return f"""Review PR #{pr.number}: {pr.title}

Base: {pr.base_branch}
Head: {pr.head_branch}

Body:
{pr.body or "No description provided"}

Diff:
{diff}

请给出结构化代码审查：风险、回归、遗漏测试、建议。"""

    def _run_codex_review(self, prompt: str) -> str:
        """Run codex to generate review.

        Args:
            prompt: Review prompt

        Returns:
            Review content

        Raises:
            RuntimeError: If codex execution fails
        """
        try:
            result = subprocess.run(
                ["codex", "exec", "--full-auto", prompt],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Codex execution failed: {e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError(
                "Codex not found. Please install: npm install -g @openai/codex"
            )
