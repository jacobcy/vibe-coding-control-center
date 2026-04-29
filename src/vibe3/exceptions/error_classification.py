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
)


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
    if (
        "rate limit" in output_lower
        or "rate_limit" in output_lower
        or "429" in output_lower
        or "toomanyrequests" in output_lower
        or "too many requests" in output_lower
    ):
        return E_API_RATE_LIMIT
    if "timeout" in output_lower or "timed out" in output_lower:
        return E_API_TIMEOUT
    if (
        "service unavailable" in output_lower
        or "serveroverloaded" in output_lower
        or "server overloaded" in output_lower
        or "503" in output_lower
    ):
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
