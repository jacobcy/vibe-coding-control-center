"""Command dispatcher."""

import subprocess
from pathlib import Path

from loguru import logger

from vibe3.orchestra.models import Trigger


class Dispatcher:
    """Dispatches commands based on triggers."""

    def __init__(self, dry_run: bool = False, repo_path: Path | None = None):
        self.dry_run = dry_run
        self.repo_path = repo_path or Path.cwd()

    def dispatch(self, trigger: Trigger) -> bool:
        """Execute command for trigger.

        Args:
            trigger: Trigger to dispatch

        Returns:
            True if successful, False otherwise
        """
        log = logger.bind(
            domain="orchestra",
            action="dispatch",
            issue=trigger.issue.number,
            command=trigger.command,
        )

        cmd = self._build_command(trigger)
        log.info(f"Dispatching: {' '.join(cmd)}")

        if self.dry_run:
            log.info("Dry run, skipping execution")
            return True

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=3600,
            )

            if result.returncode != 0:
                log.error(f"Command failed: {result.stderr}")
                return False

            log.info("Command completed successfully")
            return True

        except subprocess.TimeoutExpired:
            log.error("Command timed out")
            return False
        except Exception as e:
            log.error(f"Command error: {e}")
            return False

    def _build_command(self, trigger: Trigger) -> list[str]:
        """Build command list from trigger."""
        cmd = ["uv", "run", "python", "-m", "vibe3", trigger.command]
        cmd.extend(trigger.args)

        if trigger.command == "plan" and "task" in trigger.args:
            cmd.append(str(trigger.issue.number))

        return cmd
