"""Command execution machinery for Orchestra."""

import subprocess
from pathlib import Path

from loguru import logger

from vibe3.runtime.circuit_breaker import CircuitBreaker, classify_failure

_DISPATCH_TIMEOUT = 3600


def run_command(
    cmd: list[str],
    cwd: Path,
    label: str,
    circuit_breaker: CircuitBreaker | None = None,
) -> tuple[bool, str | None]:
    """Execute a subprocess command with timeout and structured logging.

    Returns:
        (success, error_category)
    """
    # Check circuit breaker before dispatch
    if circuit_breaker and not circuit_breaker.allow_request():
        logger.bind(domain="orchestra").warning(f"{label} blocked by circuit breaker")
        return False, "circuit_breaker"

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=_DISPATCH_TIMEOUT,
        )
        if result.returncode != 0:
            logger.bind(domain="orchestra").error(f"{label} failed: {result.stderr}")
            # Record failure for circuit breaker
            category = classify_failure(
                result.returncode, result.stderr or "", timed_out=False
            )
            if circuit_breaker:
                circuit_breaker.record_failure(category)
            return False, category

        logger.bind(domain="orchestra").info(f"{label} completed successfully")
        # Record success for circuit breaker
        if circuit_breaker:
            circuit_breaker.record_success()
        return True, None

    except subprocess.TimeoutExpired:
        logger.bind(domain="orchestra").error(f"{label} timed out")
        category = classify_failure(returncode=1, stderr="timeout", timed_out=True)
        if circuit_breaker:
            circuit_breaker.record_failure(category)
        return False, category

    except Exception as e:
        logger.bind(domain="orchestra").error(f"{label} error: {e}")
        category = classify_failure(returncode=1, stderr=str(e), timed_out=False)
        if circuit_breaker:
            circuit_breaker.record_failure(category)
        return False, category
