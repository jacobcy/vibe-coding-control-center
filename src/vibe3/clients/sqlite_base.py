"""Shared SQLite client bootstrap and connection helpers."""

import atexit
import sqlite3
import threading
from pathlib import Path
from typing import Protocol

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.exceptions import GitError

# Module-level singleton connection to avoid FD exhaustion
# Shared across all SQLiteClient instances
_global_conn: sqlite3.Connection | None = None
_global_db_path: str | None = None
_global_lock = threading.Lock()


class _HasConnection(Protocol):
    """Protocol for repo mixins that have _get_connection method."""

    db_path: str

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        ...


def _get_global_connection(db_path: str) -> sqlite3.Connection:
    """Get or create the module-level singleton database connection.

    Uses a single global connection shared by all SQLiteClient instances
    to avoid FD exhaustion from repeated open/close on every operation.

    Thread-safe: Uses threading.Lock and check_same_thread=False.
    """
    global _global_conn, _global_db_path

    with _global_lock:
        # Reopen if path changed or connection is None
        if _global_conn is None or _global_db_path != db_path:
            if _global_conn is not None:
                try:
                    _global_conn.close()
                except Exception:
                    pass
            _global_conn = sqlite3.connect(db_path, check_same_thread=False)
            _global_db_path = db_path

    return _global_conn


def _close_global_connection() -> None:
    """Close the global singleton connection."""
    global _global_conn, _global_db_path
    if _global_conn is not None:
        try:
            _global_conn.close()
        except Exception:
            pass
        _global_conn = None
        _global_db_path = None


atexit.register(_close_global_connection)


class SQLiteClientBase:
    """Connection/bootstrap layer shared by focused SQLite repositories."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            git_common_dir = GitClient().get_git_common_dir()
            if not git_common_dir:
                raise GitError("rev-parse --git-common-dir", "returned empty path")

            git_dir = Path(git_common_dir)
            if not git_dir.is_absolute():
                raise GitError(
                    "rev-parse --git-common-dir",
                    f"returned non-absolute path: {git_dir}",
                )
            vibe3_dir = git_dir / "vibe3"
            vibe3_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(vibe3_dir / "handoff.db")

        self.db_path = db_path
        self._init_db()
        logger.bind(external="sqlite", operation="init", db_path=db_path).debug(
            "SQLite client initialized"
        )

    def _init_db(self) -> None:
        """Initialize schema using singleton connection (thread-safe)."""
        conn = _get_global_connection(self.db_path)
        with _global_lock:
            # Check if schema already initialized (thread-safe check)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='schema_meta'"
            )
            if cursor.fetchone() is None:
                # Schema not initialized yet, do it now (protected by lock)
                init_schema(conn)

    def _get_connection(self) -> sqlite3.Connection:
        """Get the global singleton connection for this database."""
        return _get_global_connection(self.db_path)
