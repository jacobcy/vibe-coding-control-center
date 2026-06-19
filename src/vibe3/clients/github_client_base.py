"""GitHub client base functionality."""

import os
import subprocess
from typing import NoReturn

from loguru import logger

from vibe3.exceptions import GitHubError, UserError

# Standard timeout for GitHub CLI API calls (seconds)
GH_API_TIMEOUT = 30


def raise_gh_pr_error(
    error: subprocess.CalledProcessError,
    operation: str,
    user_tips: str | None = None,
) -> NoReturn:
    """Normalize gh pr command failure into unified error types."""
    error_msg = (error.stderr or error.stdout or f"Failed to {operation}").strip()
    lower_msg = error_msg.lower()

    recoverable_patterns = (
        "already exists",
        "no commits between",
        "must push the current branch",
        "head sha can't be blank",
        "already ready for review",
        "is in draft mode",
        "is not mergeable",
        "checks are failing",
        "no pull requests found",
    )
    if any(pattern in lower_msg for pattern in recoverable_patterns):
        tips = f"\nTips:\n{user_tips}" if user_tips else ""
        raise UserError(f"PR {operation} failed: {error_msg}{tips}") from error

    raise GitHubError(
        status_code=error.returncode,
        message=f"gh pr {operation} failed: {error_msg}",
    ) from error


class GitHubClientBase:
    """Base class for GitHub client operations.

    Token Management:
        This class does NOT manage tokens explicitly. Instead, it relies on
        environment variable injection at the execution layer:

        1. Role builder injects token into ExecutionRequest.env["GH_TOKEN"]
        2. tmux session receives the environment variables
        3. All subprocess.run(["gh", ...]) automatically inherit GH_TOKEN

        This design keeps the client simple and leverages Unix process environment
        inheritance, making token isolation transparent to the client code.
    """

    def check_auth(self) -> bool:
        """Check if authenticated to GitHub.

        Strategy:
        1. If GH_TOKEN is set, verify it works by testing API access
        2. Otherwise, check gh auth status

        This approach is more robust than relying solely on 'gh auth status'
        return code, which can fail due to keyring warnings even when GH_TOKEN
        is valid and functional.
        """
        try:
            # If GH_TOKEN is set, test API access directly
            if os.environ.get("GH_TOKEN"):
                result = subprocess.run(
                    ["gh", "api", "user", "-q", ".login"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return result.returncode == 0 and bool(result.stdout.strip())

            # Otherwise, check gh auth status
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            logger.bind(
                external="github",
                operation="check_auth",
            ).error("Failed to check auth")
            return False

    def _run_gh_command(
        self,
        cmd: list[str],
        *,
        timeout: int | None = None,
        pager: bool = False,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str] | None:
        """Execute a gh CLI command with standard error handling.

        Args:
            cmd: Full command list (e.g. ["gh", "issue", "list", ...]).
            timeout: Seconds before timeout. Defaults to GH_API_TIMEOUT.
            pager: If True, inject GH_PAGER=cat into the subprocess env.
            input_text: Text to pass to stdin (for --input - style commands).

        Returns:
            CompletedProcess on success.
            None on any failure (TimeoutExpired, FileNotFoundError).
        """
        env = {**os.environ, "GH_PAGER": "cat"} if pager else None
        effective_timeout = timeout if timeout is not None else GH_API_TIMEOUT
        stdin_input = subprocess.PIPE if input_text is not None else None
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                env=env,
                input=input_text,
                stdin=stdin_input,
            )
        except subprocess.TimeoutExpired:
            logger.bind(external="github", cmd=" ".join(cmd[:3])).warning(
                f"gh command timed out after {effective_timeout}s"
            )
            return None
        except FileNotFoundError:
            logger.bind(external="github").warning("gh CLI not found")
            return None

    def get_current_user(self) -> str:
        """Get current authenticated user login name."""
        try:
            result = subprocess.run(
                ["gh", "api", "user", "-q", ".login"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"Failed to get current GitHub user: {error_msg}",
            ) from e

    def _extract_pr_number(self, pr_url: str) -> int:
        """Extract PR number from URL."""
        # URL format: https://github.com/owner/repo/pull/123
        parts = pr_url.split("/")
        if len(parts) < 7 or parts[-2] != "pull":
            raise ValueError(f"Invalid PR URL: {pr_url}")
        return int(parts[-1])
