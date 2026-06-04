"""Error classification functions.

Classify errors from backend output and determine if they should trigger failed gate.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.exceptions import (
    AgentExecutionError,
    AgentPresetNotFoundError,
    InvalidBranchLinkError,
    MissingResourceError,
)
from vibe3.exceptions.error_codes import (
    E_API_NETWORK,
    E_API_RATE_LIMIT,
    E_API_TIMEOUT,
    E_API_UNAVAILABLE,
    E_API_UNKNOWN,
    E_CAPACITY_SKIP,
    E_CONFIG_MISSING,
    E_DISPATCH_FAILURE,
    E_EXEC_FLOW_FAILURE,
    E_EXEC_NO_OUTPUT,
    E_EXEC_UNKNOWN,
    E_INVALID_BRANCH_LINK,
    E_MODEL_CONFIG,
    E_MODEL_NOT_FOUND,
    E_MODEL_PERMISSION,
)
from vibe3.exceptions.error_severity import ErrorHandlingContract, ErrorSeverity
from vibe3.exceptions.runtime_errors import APIError, GitHubAPIError

if TYPE_CHECKING:
    pass

# Exception type → error code mapping for caught exceptions
EXCEPTION_TO_ERROR_CODE: dict[type[BaseException], str] = {
    # Standard library
    asyncio.TimeoutError: E_API_TIMEOUT,
    TimeoutError: E_API_TIMEOUT,
    ConnectionError: E_API_NETWORK,
    ConnectionRefusedError: E_API_NETWORK,
    # vibe3 exceptions
    AgentExecutionError: E_EXEC_UNKNOWN,
    AgentPresetNotFoundError: E_MODEL_CONFIG,
    InvalidBranchLinkError: E_INVALID_BRANCH_LINK,
    MissingResourceError: E_CONFIG_MISSING,
    # Runtime infrastructure errors
    GitHubAPIError: E_API_UNAVAILABLE,
    APIError: E_API_UNKNOWN,
}

# Exception name → error code mapping for string matching (supplements current logic)
EXCEPTION_NAME_TO_ERROR_CODE: dict[str, str] = {
    "ProviderModelNotFoundError": E_MODEL_NOT_FOUND,
    "RateLimitError": E_API_RATE_LIMIT,
    "AuthenticationError": E_MODEL_CONFIG,
    "PermissionDeniedError": E_MODEL_PERMISSION,
}


def classify_error_from_exception(exc: BaseException) -> str:
    """Classify error from exception instance.

    Checks exception type first, then exception name string.
    Returns E_EXEC_UNKNOWN if no match found.
    """
    # Try exception type mapping
    for exc_type, code in EXCEPTION_TO_ERROR_CODE.items():
        if isinstance(exc, exc_type):
            return code

    # Try exception name mapping
    exc_name = type(exc).__name__
    if exc_name in EXCEPTION_NAME_TO_ERROR_CODE:
        return EXCEPTION_NAME_TO_ERROR_CODE[exc_name]

    return E_EXEC_UNKNOWN


def classify_error_hybrid(exc: BaseException) -> str:
    """Hybrid classification: try exception first, then string fallback.

    Use when you have the exception instance available.
    """
    # Try structured classification first
    code = classify_error_from_exception(exc)
    if code != E_EXEC_UNKNOWN:
        return code

    # Fallback to string matching
    return classify_error(f"{type(exc).__name__}: {exc}")


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
        or "server is overloaded" in output_lower
        or "decode server is overloaded" in output_lower
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

    # Capacity control - normal skip (not an error)
    if "tmux session" in output_lower and "already exists" in output_lower:
        return E_CAPACITY_SKIP

    # Fallback with warning for unclassified errors
    logger.bind(
        domain="error_tracking",
        error_output=error_output[:100],  # Truncate for logging
    ).warning("Unclassified error, defaulting to E_EXEC_UNKNOWN")
    return E_EXEC_UNKNOWN


# Error registry: maps error codes to handling contracts
ERROR_REGISTRY: dict[str, ErrorHandlingContract] = {
    # WARNING: Configuration/asset missing errors - recorded to error_log
    E_CONFIG_MISSING: ErrorHandlingContract(
        code=E_CONFIG_MISSING,
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
        description="Required configuration or runtime asset missing",
    ),
    # CRITICAL: Model configuration errors - immediate failed gate
    # NOTE: CRITICAL severity only affects FailedGate, NOT flow block
    # Flow block is determined by business logic, not runtime errors
    E_MODEL_NOT_FOUND: ErrorHandlingContract(
        code=E_MODEL_NOT_FOUND,
        severity=ErrorSeverity.CRITICAL,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="immediate",
        description="Model not found or unavailable",
    ),
    E_MODEL_PERMISSION: ErrorHandlingContract(
        code=E_MODEL_PERMISSION,
        severity=ErrorSeverity.CRITICAL,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="immediate",
        description="Permission denied for model access",
    ),
    E_MODEL_CONFIG: ErrorHandlingContract(
        code=E_MODEL_CONFIG,
        severity=ErrorSeverity.CRITICAL,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="immediate",
        description="Model configuration error",
    ),
    # ERROR: API errors - threshold-based failed gate
    # NOTE: ERROR severity only affects FailedGate, NOT flow block
    E_API_RATE_LIMIT: ErrorHandlingContract(
        code=E_API_RATE_LIMIT,
        severity=ErrorSeverity.ERROR,
        counts_toward_threshold=True,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="threshold",
        description="API rate limit exceeded",
    ),
    E_API_TIMEOUT: ErrorHandlingContract(
        code=E_API_TIMEOUT,
        severity=ErrorSeverity.ERROR,
        counts_toward_threshold=True,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="threshold",
        description="API request timeout",
    ),
    E_API_UNAVAILABLE: ErrorHandlingContract(
        code=E_API_UNAVAILABLE,
        severity=ErrorSeverity.ERROR,
        counts_toward_threshold=True,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="threshold",
        description="API service unavailable",
    ),
    E_API_NETWORK: ErrorHandlingContract(
        code=E_API_NETWORK,
        severity=ErrorSeverity.ERROR,
        counts_toward_threshold=True,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="threshold",
        description="Network connection error",
    ),
    E_API_UNKNOWN: ErrorHandlingContract(
        code=E_API_UNKNOWN,
        severity=ErrorSeverity.ERROR,
        counts_toward_threshold=True,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",  # No flow block for runtime errors
        gate_action="threshold",
        description="Unknown API error",
    ),
    # WARNING: Execution diagnostics - recorded/surfaced, no gate activation
    E_EXEC_UNKNOWN: ErrorHandlingContract(
        code=E_EXEC_UNKNOWN,
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
        description="Unrecognized execution error (test leak or transient)",
    ),
    E_EXEC_NO_OUTPUT: ErrorHandlingContract(
        code=E_EXEC_NO_OUTPUT,
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
        description="Agent execution produced no output",
    ),
    E_DISPATCH_FAILURE: ErrorHandlingContract(
        code=E_DISPATCH_FAILURE,
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
        description=(
            "Dispatch infrastructure failure (worktree/launch) "
            "— does not block orchestra"
        ),
    ),
    E_EXEC_FLOW_FAILURE: ErrorHandlingContract(
        code=E_EXEC_FLOW_FAILURE,
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
        description="Flow execution failure (runtime, no block)",
    ),
    E_CAPACITY_SKIP: ErrorHandlingContract(
        code=E_CAPACITY_SKIP,
        severity=ErrorSeverity.WARNING,
        counts_toward_threshold=False,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="ignore",
        description="Capacity control skip (not an error)",
    ),
    E_INVALID_BRANCH_LINK: ErrorHandlingContract(
        code=E_INVALID_BRANCH_LINK,
        severity=ErrorSeverity.ERROR,
        counts_toward_threshold=True,
        record_in_error_log=True,
        write_timeline_event=True,
        issue_action="record_only",
        gate_action="threshold",
        description="Invalid branch linked to issue in flow_issue_links",
    ),
}


def get_error_handling_contract(error_code: str) -> ErrorHandlingContract:
    """Get handling contract for an error code.

    Args:
        error_code: Error code (E_MODEL_*, E_API_*, E_EXEC_*, E_CAPACITY_*)

    Returns:
        ErrorHandlingContract with severity and handling metadata

    Note:
        Unregistered codes return a fallback ERROR contract for backward
        compatibility during migration.
    """
    if error_code not in ERROR_REGISTRY:
        # Fallback for unregistered codes: record_only (no flow block)
        # Runtime errors never trigger flow block regardless of registry status
        logger.bind(
            domain="error_tracking",
            error_code=error_code,
        ).warning(
            f"Unregistered error code {error_code}, "
            "using fallback ERROR contract (record_only)"
        )
        return ErrorHandlingContract(
            code=error_code,
            severity=ErrorSeverity.ERROR,
            counts_toward_threshold=True,
            record_in_error_log=True,
            write_timeline_event=True,
            issue_action="record_only",
            gate_action="threshold",
            description=f"Unregistered error code: {error_code}",
        )

    return ERROR_REGISTRY[error_code]
