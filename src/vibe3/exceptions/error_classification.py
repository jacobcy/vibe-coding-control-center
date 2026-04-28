"""Error classification functions.

Classify errors from backend output and determine if they should trigger failed gate.
"""

from __future__ import annotations

from loguru import logger

from vibe3.exceptions.error_codes import (
    E_API_NETWORK,
    E_API_RATE_LIMIT,
    E_API_TIMEOUT,
    E_API_UNAVAILABLE,
    E_API_UNKNOWN,
    E_EXEC_NO_OUTPUT,
    E_EXEC_UNKNOWN,
    E_MODEL_CONFIG,
    E_MODEL_NOT_FOUND,
    E_MODEL_PERMISSION,
    is_api_error,
    is_model_error,
)
from vibe3.exceptions.error_tracking import ErrorTrackingService


def classify_error(error_output: str) -> str:
    """Classify error from backend output.

    Args:
        error_output: Combined stdout/stderr from codeagent

    Returns:
        Error code (E_MODEL_*, E_API_*, E_EXEC_*)

    Classification rules:
    - ProviderModelNotFoundError → E_MODEL_NOT_FOUND
    - Permission denied → E_MODEL_PERMISSION
    - Rate limit → E_API_RATE_LIMIT
    - Timeout → E_API_TIMEOUT
    - Service unavailable → E_API_UNAVAILABLE
    - Network error → E_API_NETWORK
    - No output → E_EXEC_NO_OUTPUT
    - Other → E_EXEC_UNKNOWN
    """
    output_lower = error_output.lower()

    # Model config errors
    if "providermodelnotfounderror" in output_lower:
        return E_MODEL_NOT_FOUND
    if "model not found" in output_lower:
        return E_MODEL_NOT_FOUND
    if "permission denied" in output_lower and "model" in output_lower:
        return E_MODEL_PERMISSION
    if "invalid api key" in output_lower:
        return E_MODEL_CONFIG

    # API errors
    if "rate limit" in output_lower:
        return E_API_RATE_LIMIT
    if "timeout" in output_lower or "timed out" in output_lower:
        return E_API_TIMEOUT
    if "service unavailable" in output_lower or "503" in output_lower:
        return E_API_UNAVAILABLE
    if "network error" in output_lower or "connection refused" in output_lower:
        return E_API_NETWORK
    if "api error" in output_lower:
        return E_API_UNKNOWN

    # Execution errors
    if "no output" in output_lower or "completed without agent_message" in output_lower:
        return E_EXEC_NO_OUTPUT

    # Fallback with warning for unclassified errors
    logger.bind(
        domain="error_tracking",
        error_output=error_output[:100],  # Truncate for logging
    ).warning("Unclassified error, defaulting to E_EXEC_UNKNOWN")
    return E_EXEC_UNKNOWN


def should_trigger_failed_gate(
    error_code: str,
    error_tracking: ErrorTrackingService | None = None,
) -> tuple[bool, str]:
    """Determine if error should trigger global failed gate.

    Args:
        error_code: Error code from classify_error()
        error_tracking: ErrorTrackingService instance (defaults to global instance)

    Returns:
        (trigger_gate: bool, reason: str)

    Logic:
    - E_MODEL_* → immediate failed gate (config error)
    - E_API_* → check threshold (2+ in 3 ticks)
    - E_EXEC_* → local blocked only
    """
    effective_tracking = error_tracking or ErrorTrackingService.get_instance()

    # Model config errors → immediate failed gate
    if is_model_error(error_code):
        logger.bind(
            domain="error_tracking",
            error_code=error_code,
        ).warning("Model config error → failed gate")
        return True, f"Model config error: {error_code}"

    # API errors → check threshold
    if is_api_error(error_code):
        threshold_reached, count = effective_tracking.record_error(
            error_code, error_message=""  # Empty message for threshold check
        )

        if threshold_reached:
            logger.bind(
                domain="error_tracking",
                error_code=error_code,
                window_count=count,
            ).error("API error threshold reached → failed gate")
            return (
                True,
                (
                    f"API error threshold: {count} errors in "
                    f"{ErrorTrackingService.TIME_WINDOW_MINUTES} minutes"
                ),
            )
        else:
            logger.bind(
                domain="error_tracking",
                error_code=error_code,
                window_count=count,
            ).info("Sporadic API error → local blocked")
            return (
                False,
                (
                    f"Sporadic API error: {error_code} "
                    f"(count: {count}/{ErrorTrackingService.THRESHOLD_COUNT})"
                ),
            )

    # Execution errors → local blocked only
    logger.bind(
        domain="error_tracking",
        error_code=error_code,
    ).info("Execution error → local blocked")
    return False, f"Execution error: {error_code}"
