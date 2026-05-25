"""Branch comparison utilities for PR operations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient


@dataclass(frozen=True)
class BranchBehindInfo:
    """Information about how far a branch is behind its base."""

    head_branch: str
    base_branch: str
    behind_count: int
    behind_commits: list[str]


def check_branch_behind(
    git_client: "GitClient",
    head_branch: str,
    base_branch: str,
) -> BranchBehindInfo | None:
    """Check if a branch is behind its base branch.

    Args:
        git_client: GitClient instance
        head_branch: PR head branch name
        base_branch: PR base branch name

    Returns:
        BranchBehindInfo if behind, None if up-to-date or error
    """
    try:
        # origin/head_branch..origin/base_branch = commits in base
        # that are NOT in head (i.e., behind count)
        behind_commits = git_client.get_commit_subjects(
            base_ref=f"origin/{head_branch}",
            head_ref=f"origin/{base_branch}",
        )

        if not behind_commits:
            return None

        return BranchBehindInfo(
            head_branch=head_branch,
            base_branch=base_branch,
            behind_count=len(behind_commits),
            behind_commits=behind_commits,
        )
    except Exception as e:
        logger.bind(
            domain="pr",
            action="check_branch_behind",
            head_branch=head_branch,
            base_branch=base_branch,
            error_type=type(e).__name__,
            error_msg=str(e),
        ).debug(f"Failed to check branch behind: {e}")
        return None


def format_branch_behind_body(info: BranchBehindInfo) -> str:
    """Format branch behind info as markdown for PR body.

    Args:
        info: BranchBehindInfo instance

    Returns:
        Markdown formatted warning block
    """
    return f"""## ⚠️ Branch Behind Base

The PR branch `{info.head_branch}` is behind `{info.base_branch}` \
by **{info.behind_count} commit(s)**.

### Recommended Actions

```bash
git fetch origin {info.base_branch}
git rebase origin/{info.base_branch}
git push --force-with-lease origin {info.head_branch}
```
"""


def format_branch_behind_console(info: BranchBehindInfo) -> str:
    """Format branch behind info for console display (Rich markup).

    Args:
        info: BranchBehindInfo instance

    Returns:
        Rich markup formatted string
    """
    return f"""[bold red]⚠️  Branch Behind Base[/]

  [bold red]PR branch[/] [yellow]{info.head_branch}[/]
  [bold red]is behind[/] [cyan]{info.base_branch}[/]
  [bold red]by[/] [bold yellow]{info.behind_count} commit(s)[/]

[bold cyan]Recommended actions:[/]
  [green]1.[/] git fetch origin {info.base_branch}
  [green]2.[/] git rebase origin/{info.base_branch}
  [green]3.[/] git push --force-with-lease origin {info.head_branch}"""
