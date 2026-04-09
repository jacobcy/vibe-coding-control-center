"""Agent CLI command builder.

Shared utility for constructing CLI commands for agent execution.
Extracted from StateLabelDispatchService._build_command() for reuse.
"""

from pathlib import Path


def _get_cli_entry() -> str:
    """Get CLI entry point path.

    Returns:
        Path to vibe3 CLI entry point
    """
    return str(Path(__file__).resolve().parents[3] / "src" / "vibe3" / "cli.py")


def _get_repo_root() -> str:
    """Get repository root path.

    Returns:
        Path to repository root
    """
    return str(Path(__file__).resolve().parents[3])


class AgentCommandBuilder:
    """Shared utility for building agent CLI commands.

    Provides static methods for constructing CLI commands for
    planner, executor, and reviewer agents.

    Usage:
        cmd = AgentCommandBuilder.build_plan_command(issue_number=42)
        # Returns: ["uv", "run", "--project", "/path/to/repo", "python", ...]
    """

    @staticmethod
    def build_plan_command(issue_number: int) -> list[str]:
        """Build vibe3 plan command.

        Args:
            issue_number: GitHub issue number

        Returns:
            CLI command as list of strings

        Example:
            >>> AgentCommandBuilder.build_plan_command(42)
            ["uv", "run", "--project", "/repo", "python", "-I",
             "cli.py", "plan", "--issue", "42", "--no-async"]
        """
        cli_entry = _get_cli_entry()
        repo_root = _get_repo_root()

        return [
            "uv",
            "run",
            "--project",
            repo_root,
            "python",
            "-I",
            cli_entry,
            "plan",
            "--issue",
            str(issue_number),
            "--no-async",
        ]

    @staticmethod
    def build_run_command(plan_file: str) -> list[str]:
        """Build vibe3 run command.

        Args:
            plan_file: Path to plan file

        Returns:
            CLI command as list of strings

        Example:
            >>> AgentCommandBuilder.build_run_command(".agent/plans/plan.md")
            ["uv", "run", "--project", "/repo", "python", "-I",
             "cli.py", "run", "--plan", "plan.md"]
        """
        cli_entry = _get_cli_entry()
        repo_root = _get_repo_root()

        return [
            "uv",
            "run",
            "--project",
            repo_root,
            "python",
            "-I",
            cli_entry,
            "run",
            "--plan",
            plan_file,
        ]

    @staticmethod
    def build_review_command() -> list[str]:
        """Build vibe3 review command.

        Returns:
            CLI command as list of strings

        Example:
            >>> AgentCommandBuilder.build_review_command()
            ["uv", "run", "--project", "/repo", "python", "-I", "cli.py", "review"]
        """
        cli_entry = _get_cli_entry()
        repo_root = _get_repo_root()

        return [
            "uv",
            "run",
            "--project",
            repo_root,
            "python",
            "-I",
            cli_entry,
            "review",
        ]
