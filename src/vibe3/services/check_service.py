"""Check service implementation."""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient


@dataclass
class CheckResult:
    """Result of consistency check."""

    is_valid: bool
    issues: list[str]


@dataclass
class FixResult:
    """Result of auto-fix."""

    success: bool
    error: str | None = None


class CheckService:
    """Service for verifying handoff store consistency."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        """Initialize check service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
            github_client: GitHubClient instance for GitHub operations
        """
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()

    def verify_current_flow(self, fix: bool = False) -> CheckResult:
        """Verify current flow consistency.

        Args:
            fix: Whether to auto-fix issues

        Returns:
            Check result with issues list
        """
        logger.bind(domain="check", action="verify").info("Verifying flow consistency")

        branch = self.git_client.get_current_branch()
        issues: list[str] = []

        # Check 1: Flow exists
        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            issues.append(f"No flow record for branch '{branch}'")
            return CheckResult(is_valid=False, issues=issues)

        # Check 2: Task issue exists on GitHub
        task_issue = flow_data.get("task_issue_number")
        if task_issue:
            issue = self.github_client.view_issue(task_issue)
            if not issue:
                issues.append(f"Task issue #{task_issue} not found on GitHub")

        # Check 3: Only one task issue per branch
        issue_links = self.store.get_issue_links(branch)
        task_issues = [link for link in issue_links if link["issue_role"] == "task"]
        if len(task_issues) > 1:
            issues.append(f"Multiple task issues for branch '{branch}'")

        # Check 4: PR matches branch
        pr_number = flow_data.get("pr_number")
        if pr_number:
            pr = self.github_client.get_pr(pr_number)
            if pr and pr.head_branch != branch:
                issues.append(f"PR #{pr_number} does not match branch '{branch}'")

        # Check 5: Ref files exist
        for ref_field in ["plan_ref", "report_ref", "audit_ref"]:
            ref_value = flow_data.get(ref_field)
            if ref_value:
                ref_path = Path(ref_value)
                if not ref_path.exists():
                    issues.append(f"{ref_field} file not found: {ref_value}")

        # Check 6: Shared current.md exists
        git_dir = self.git_client.get_git_common_dir()
        branch_safe = branch.replace("/", "-").replace("\\", "-")
        handoff_path = Path(git_dir) / "vibe3" / "handoff" / branch_safe / "current.md"
        if not handoff_path.exists():
            issues.append(f"Shared handoff file not found: {handoff_path}")

        is_valid = len(issues) == 0
        logger.bind(is_valid=is_valid, issues_count=len(issues)).info("Check completed")

        return CheckResult(is_valid=is_valid, issues=issues)

    def auto_fix(self, issues: list[str]) -> FixResult:
        """Auto-fix identified issues.

        Args:
            issues: List of issues to fix

        Returns:
            Fix result
        """
        logger.bind(domain="check", action="auto_fix").info("Auto-fixing issues")

        raise NotImplementedError(
            "Auto-fix functionality is not yet implemented. "
            "Please fix issues manually or use specific fix commands."
        )
