"""Dead code detection rules.

This module defines the rules for classifying code as dead (unused).
"""

import re
from typing import Literal

from loguru import logger

# Exclusion patterns - symbols that should not be flagged as dead code
EXCLUDE_PATTERNS = [
    # Test functions (pytest)
    r"^test_",
    r"^_test$",
    # Setup/teardown (pytest, setuptools)
    r"^setup$",
    r"^teardown$",
    r"^setup_module$",
    r"^teardown_module$",
    r"^setup_class$",
    r"^teardown_class$",
    r"^setup_method$",
    r"^teardown_method$",
    # Special methods (Python magic methods)
    r"^__\w+__$",
    # Entry points
    r"^main$",
    # Type annotations (may be used by type checkers)
    r"^__all__$",
]

# Private function pattern (lower confidence)
PRIVATE_PATTERN = r"^_"


def should_exclude(symbol_name: str) -> bool:
    """Check if a symbol should be excluded from dead code detection.

    Args:
        symbol_name: Name of the symbol (function/class/method)

    Returns:
        True if the symbol should be excluded
    """
    for pattern in EXCLUDE_PATTERNS:
        if re.match(pattern, symbol_name):
            logger.bind(
                domain="dead_code_rules",
                action="should_exclude",
                symbol=symbol_name,
                pattern=pattern,
            ).debug("Symbol excluded by pattern")
            return True
    return False


def is_private(symbol_name: str) -> bool:
    """Check if a symbol is private (starts with _).

    Args:
        symbol_name: Name of the symbol

    Returns:
        True if the symbol is private
    """
    return bool(re.match(PRIVATE_PATTERN, symbol_name))


def classify_confidence(
    symbol_name: str,
    ref_count: int,
    is_cli_command: bool = False,
) -> Literal["high", "medium", "low", "excluded"]:
    """Classify the confidence level of a dead code finding.

    Args:
        symbol_name: Name of the symbol
        ref_count: Number of references found
        is_cli_command: Whether the symbol is a CLI command

    Returns:
        Confidence level: "high", "medium", "low", or "excluded"
    """
    # Exclude CLI commands and special patterns
    if is_cli_command or should_exclude(symbol_name):
        return "excluded"

    # Only classify as dead if ref_count == 0
    if ref_count > 0:
        logger.bind(
            domain="dead_code_rules",
            action="classify_confidence",
            symbol=symbol_name,
            ref_count=ref_count,
        ).debug("Symbol has references, not dead code")
        return "excluded"

    # High confidence: regular functions with 0 refs
    if not is_private(symbol_name):
        return "high"

    # Medium confidence: private functions with 0 refs
    # (might be used dynamically)
    return "medium"


def is_dead_code(
    symbol_name: str,
    ref_count: int,
    is_cli_command: bool = False,
) -> tuple[bool, str]:
    """Determine if a symbol is dead code.

    Args:
        symbol_name: Name of the symbol
        ref_count: Number of references found
        is_cli_command: Whether the symbol is a CLI command

    Returns:
        Tuple of (is_dead: bool, reason: str)
    """
    confidence = classify_confidence(symbol_name, ref_count, is_cli_command)

    if confidence == "excluded":
        if is_cli_command:
            return False, "CLI command (invoked via CLI, not code)"
        if should_exclude(symbol_name):
            return False, "Excluded pattern (test/special method)"
        return False, f"Has {ref_count} references"

    if confidence == "high":
        return True, "Unused function with 0 references (high confidence)"

    if confidence == "medium":
        return True, "Unused private function with 0 references (medium confidence)"

    return False, "Not dead code"
