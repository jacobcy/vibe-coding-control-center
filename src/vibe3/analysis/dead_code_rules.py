"""Dead code detection rules.

This module defines the rules for classifying code as dead (unused).
"""

import ast
import re
from pathlib import Path
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
    # Webhook handlers (invoked by external systems, not code)
    r"^handle_\w+_webhook$",
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


def get_router_functions(file_path: str, tree: ast.Module | None = None) -> set[str]:
    """Extract all FastAPI router-decorated function names from a file.

    Args:
        file_path: Relative file path
        tree: Optional pre-parsed AST module. If None, file will be read and parsed.

    Returns:
        Set of function names that have @router.post/get/put/delete decorators
    """
    try:
        if tree is None:
            source = Path(file_path).read_text(encoding="utf-8")
            tree = ast.parse(source)
        result: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    # Check decorator patterns:
                    # @router.post(...)
                    # @router.get(...)
                    # @app.post(...)
                    # etc.
                    if isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute):
                            attr_name = decorator.func.attr
                            if attr_name in (
                                "post",
                                "get",
                                "put",
                                "delete",
                                "patch",
                            ):
                                if isinstance(decorator.func.value, ast.Name):
                                    # router.post, app.post, etc.
                                    result.add(node.name)
                                    break
                    # Also check @router.post without call
                    elif isinstance(decorator, ast.Attribute):
                        if decorator.attr in (
                            "post",
                            "get",
                            "put",
                            "delete",
                            "patch",
                        ):
                            result.add(node.name)
                            break
        return result
    except Exception:
        # If parsing fails, assume no router decorators
        return set()


def classify_confidence(
    symbol_name: str,
    ref_count: int,
    is_cli_command: bool = False,
    router_funcs: set[str] | None = None,
) -> Literal["high", "medium", "low", "excluded"]:
    """Classify the confidence level of a dead code finding.

    Args:
        symbol_name: Name of the symbol
        ref_count: Number of references found
        is_cli_command: Whether the symbol is a CLI command
        router_funcs: Set of router-decorated function names (for exclusion check)

    Returns:
        Confidence level: "high", "medium", "low", or "excluded"
    """
    # Exclude CLI commands and special patterns
    if is_cli_command or should_exclude(symbol_name):
        return "excluded"

    # Exclude functions with router decorators (FastAPI endpoints)
    if router_funcs is not None and symbol_name in router_funcs:
        logger.bind(
            domain="dead_code_rules",
            action="classify_confidence",
            symbol=symbol_name,
        ).debug("Symbol has router decorator, excluded")
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
    router_funcs: set[str] | None = None,
) -> tuple[bool, str, Literal["high", "medium", "low", "excluded"]]:
    """Determine if a symbol is dead code.

    Args:
        symbol_name: Name of the symbol
        ref_count: Number of references found
        is_cli_command: Whether the symbol is a CLI command
        router_funcs: Set of router-decorated function names (for exclusion check)

    Returns:
        Tuple of (is_dead: bool, reason: str, confidence: str)
    """
    confidence = classify_confidence(
        symbol_name, ref_count, is_cli_command, router_funcs
    )

    if confidence == "excluded":
        if is_cli_command:
            return False, "CLI command (invoked via CLI, not code)", confidence
        if router_funcs is not None and symbol_name in router_funcs:
            return False, "FastAPI endpoint (invoked via HTTP router)", confidence
        if should_exclude(symbol_name):
            return False, "Excluded pattern (test/special method)", confidence
        return False, f"Has {ref_count} references", confidence

    if confidence == "high":
        return True, "Unused function with 0 references (high confidence)", confidence

    if confidence == "medium":
        return (
            True,
            "Unused private function with 0 references (medium confidence)",
            confidence,
        )

    return False, "Not dead code", confidence

    return False, "Not dead code", confidence
