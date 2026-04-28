"""Error logging to errors.log file.

Write structured error logs for monitoring and debugging.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from loguru import logger


def write_error_log(
    error_code: str,
    error_message: str,
    tick_id: int,
    log_path: Path | None = None,
) -> None:
    """Write error to errors.log.

    Args:
        error_code: Error code (E_MODEL_*, E_API_*, E_EXEC_*)
        error_message: Error message/details
        tick_id: Current tick ID
        log_path: Path to errors.log (defaults to temp/logs/orchestra/errors.log)

    Format:
        [TIMESTAMP] [TICK_<id>] <ERROR_CODE>: <error_message>
    """
    effective_path = (
        log_path or Path(__file__).parents[3] / "temp/logs/orchestra/errors.log"
    )
    effective_path.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [TICK_{tick_id}] {error_code}: {error_message}\n"

    with effective_path.open("a") as f:
        f.write(log_line)

    logger.bind(
        domain="error_tracking",
        error_code=error_code,
        tick=tick_id,
        log_path=str(effective_path),
    ).debug("Error logged to errors.log")
