"""TickDispatcher service - executes tick plans by calling internal commands."""

from typing import Any

from loguru import logger
from rich.console import Console

from vibe3.models.tick import TickPlan


class TickDispatcher:
    """Service for executing tick plans.

    TickDispatcher is responsible for:
    - Executing governance via internal governance command
    - Executing supervisor via internal apply command
    - Handling dry-run mode (print plan instead of executing)

    TickDispatcher does NOT:
    - Plan execution (that's TickPlanner's job)
    - Access orchestration facade
    - Make decisions about which phases to run (that's in TickPlan)

    The dispatcher is intentionally simple - it just executes what the plan says.
    """

    def __init__(self, config: Any | None = None) -> None:
        """Initialize TickDispatcher.

        Args:
            config: Optional orchestra configuration (not currently used,
                but kept for consistency with other services and future extensibility)
        """
        self.config = config

    def dispatch(self, plan: TickPlan) -> None:
        """Execute tick plan by calling internal commands.

        This is a sync method (not async) to match the sync execution pattern
        of run_governance_sync and run_supervisor_apply.

        Args:
            plan: TickPlan with resolved execution parameters
        """
        if plan.dry_run:
            self._print_dry_run_plan(plan)
            return

        # Execute governance phase if enabled
        if plan.governance_enabled:
            self._dispatch_governance(plan.governance_material)

        # Execute supervisor phase if enabled
        if plan.supervisor_enabled:
            # Resolve issues: scan if empty, use explicit list otherwise
            issues = plan.supervisor_issues
            if not issues:
                issues = self._scan_supervisor_candidates()
                logger.bind(domain="tick").info(
                    f"Supervisor scan found {len(issues)} candidate(s)"
                )

            self._dispatch_supervisor(issues)

    def _print_dry_run_plan(self, plan: TickPlan) -> None:
        """Print execution plan preview using Rich Console.

        Args:
            plan: TickPlan to preview
        """
        console = Console()

        console.print("\n[bold]Dry-Run: Tick Execution Plan[/bold]\n")

        if plan.governance_enabled:
            console.print("[bold]Governance:[/bold]")
            material_info = plan.governance_material or "auto"
            console.print(f"  Material: {material_info}")
            console.print()

        if plan.supervisor_enabled:
            console.print("[bold]Supervisor:[/bold]")
            if plan.supervisor_issues:
                issues_str = ", ".join(str(i) for i in plan.supervisor_issues)
                console.print(f"  Issues: [{issues_str}]")
            else:
                console.print("  Mode: scan candidates")
            console.print()

        if not plan.governance_enabled and not plan.supervisor_enabled:
            console.print("[yellow]No phases enabled in plan[/yellow]")

    def _dispatch_governance(self, material: str | None) -> None:
        """Execute governance scan via run_governance_sync.

        Args:
            material: Optional governance role to override material rotation
        """
        from vibe3.execution.governance_sync_runner import run_governance_sync

        logger.bind(domain="tick", phase="governance").info(
            f"Dispatching governance with material={material or 'auto'}"
        )

        run_governance_sync(
            tick_count=0,  # Manual tick always uses 0
            material_override=material,
            dry_run=False,
            show_prompt=False,
            session_id=None,
        )

    def _dispatch_supervisor(self, issues: list[int]) -> None:
        """Execute supervisor apply for each issue via run_supervisor_apply.

        Args:
            issues: List of issue numbers to apply supervisor
        """
        from vibe3.execution.supervisor_apply_runner import run_supervisor_apply

        logger.bind(domain="tick", phase="supervisor").info(
            f"Dispatching supervisor for {len(issues)} issue(s)"
        )

        for issue_number in issues:
            logger.bind(
                domain="tick",
                phase="supervisor",
                issue_number=issue_number,
            ).info("Dispatching supervisor apply")

            run_supervisor_apply(
                issue_number=issue_number,
                dry_run=False,
                fresh_session=True,
            )

    def _scan_supervisor_candidates(self) -> list[int]:
        """Scan GitHub for supervisor candidate issues.

        Returns:
            List of issue numbers with supervisor + state/handoff labels
        """
        from vibe3.clients.github_client import GitHubClient
        from vibe3.config.orchestra_settings import load_orchestra_config
        from vibe3.services.scan_service import fetch_supervisor_candidates

        try:
            config = load_orchestra_config()
            github = GitHubClient()
            candidates = fetch_supervisor_candidates(github, config.repo)

            # Extract issue numbers
            issue_numbers: list[int] = [
                item["number"]
                for item in candidates
                if isinstance(item.get("number"), int)
            ]

            logger.bind(domain="tick", phase="supervisor").info(
                f"Supervisor candidate scan found {len(issue_numbers)} issue(s)"
            )

            return issue_numbers

        except Exception as exc:
            logger.bind(domain="tick", phase="supervisor").error(
                f"Supervisor candidate scan failed: {exc}"
            )
            # Return empty list on error (graceful degradation)
            return []
