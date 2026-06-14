"""Error code definitions for orchestra error classification.

Error categories:
- E_MODEL_*: Model configuration errors (immediate failed gate)
- E_API_*: API errors (threshold-based failed gate)
- E_EXEC_*: Execution errors (various handling strategies)
  - E_EXEC_FLOW_FAILURE: Runtime failures recorded to error_log only (no block)
  - Other E_EXEC_*: Local blocked only
"""

from typing import Final

# Configuration/asset missing errors - WARNING, recorded to error_log
E_CONFIG_MISSING: Final[str] = "E_CONFIG_MISSING"

# Model configuration errors - immediate failed gate
E_MODEL_NOT_FOUND: Final[str] = "E_MODEL_NOT_FOUND"
E_MODEL_PERMISSION: Final[str] = "E_MODEL_PERMISSION"
E_MODEL_CONFIG: Final[str] = "E_MODEL_CONFIG"

# API errors - threshold-based failed gate (2+ in 3 ticks)
E_API_RATE_LIMIT: Final[str] = "E_API_RATE_LIMIT"
E_API_TIMEOUT: Final[str] = "E_API_TIMEOUT"
E_API_UNAVAILABLE: Final[str] = "E_API_UNAVAILABLE"
E_API_NETWORK: Final[str] = "E_API_NETWORK"
E_API_UNKNOWN: Final[str] = "E_API_UNKNOWN"

# Execution errors - local blocked only
E_EXEC_NO_OUTPUT: Final[str] = "E_EXEC_NO_OUTPUT"
E_EXEC_INVALID_HANDOFF: Final[str] = "E_EXEC_INVALID_HANDOFF"
E_EXEC_MISSING_REF: Final[str] = "E_EXEC_MISSING_REF"
E_EXEC_AUTO_SCENE_RESET: Final[str] = "E_EXEC_AUTO_SCENE_RESET"
E_EXEC_UNKNOWN: Final[str] = "E_EXEC_UNKNOWN"
E_DISPATCH_FAILURE: Final[str] = "E_DISPATCH_FAILURE"
E_EXEC_FLOW_FAILURE: Final[str] = "E_EXEC_FLOW_FAILURE"
E_ISSUE_FAILED: Final[str] = "E_ISSUE_FAILED"

# Capacity control - normal skip (not an error)
E_CAPACITY_SKIP: Final[str] = "E_CAPACITY_SKIP"

# Data integrity errors - corruption detection
E_INVALID_BRANCH_LINK: Final[str] = "E_INVALID_BRANCH_LINK"


def is_model_error(error_code: str) -> bool:
    """Check if error is a model configuration error."""
    return error_code.startswith("E_MODEL_")


def is_api_error(error_code: str) -> bool:
    """Check if error is an API error."""
    return error_code.startswith("E_API_")


def is_exec_error(error_code: str) -> bool:
    """Check if error is an execution error."""
    return error_code.startswith("E_EXEC_")
