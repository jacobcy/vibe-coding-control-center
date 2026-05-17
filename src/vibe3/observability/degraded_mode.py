"""Degraded mode management for GitHub API unavailability."""

from __future__ import annotations

from enum import Enum

from loguru import logger


class DegradedModeReason(str, Enum):
    """Reasons for entering degraded mode."""

    GITHUB_API_TIMEOUT = "github_api_timeout"
    GITHUB_API_ERROR = "github_api_error"
    NETWORK_UNREACHABLE = "network_unreachable"
    ISSUE_BODY_EMPTY = "issue_body_empty"


class DegradedModeManager:
    """Manager for degraded mode state and logging.

    Degraded mode is entered when GitHub API is unavailable.
    In degraded mode, orchestra conservatively falls back to local DB.
    """

    _instance: DegradedModeManager | None = None
    _active: bool = False
    _reason: DegradedModeReason | None = None

    def __new__(cls) -> DegradedModeManager:
        """Singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    def enter_degraded_mode(self, reason: DegradedModeReason) -> None:
        """Enter degraded mode with logging.

        Args:
            reason: Reason for entering degraded mode
        """
        self._active = True
        self._reason = reason

        logger.bind(
            domain="orchestra",
            degraded_mode=True,
            reason=reason.value,
        ).warning(
            "Entering degraded mode: GitHub API unavailable, "
            "falling back to local DB for coordination reads"
        )

    def exit_degraded_mode(self) -> None:
        """Exit degraded mode with logging."""
        if not self._active:
            return

        logger.bind(
            domain="orchestra",
            degraded_mode=False,
            previous_reason=self._reason.value if self._reason else None,
        ).info("Exiting degraded mode: GitHub API recovered")

        self._active = False
        self._reason = None

    def is_degraded(self) -> bool:
        """Check if currently in degraded mode."""
        return self._active

    def get_reason(self) -> DegradedModeReason | None:
        """Get current degraded mode reason."""
        return self._reason


def get_degraded_manager() -> DegradedModeManager:
    """Get singleton degraded mode manager."""
    return DegradedModeManager()
