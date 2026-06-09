"""Shared SQLite client bootstrap and connection helpers."""

import atexit
import datetime
import sqlite3
import threading
from pathlib import Path
from typing import Protocol, TypeVar

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.exceptions import GitError
from vibe3.utils import get_vibe3_db_path

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


def _is_connection_usable(conn: sqlite3.Connection) -> bool:
    """Return whether a sqlite connection is still open and usable."""
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return False
    return True


def _get_global_connection(db_path: str) -> sqlite3.Connection:
    """Get or create the module-level singleton database connection.

    Uses a single global connection shared by all SQLiteClient instances
    to avoid FD exhaustion from repeated open/close on every operation.

    Thread-safe: Uses threading.Lock and check_same_thread=False.
    """
    global _global_conn, _global_db_path

    with _global_lock:
        # Reopen if path changed, connection is missing, or a previous caller
        # closed the module-level singleton directly.
        if (
            _global_conn is None
            or _global_db_path != db_path
            or not _is_connection_usable(_global_conn)
        ):
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


def _utcnow_iso() -> str:
    """Return current UTC timestamp in ISO format.

    This helper ensures consistent timezone usage across all SQLite
    repository timestamp operations.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


atexit.register(_close_global_connection)


T = TypeVar("T", bound="SQLiteClientBase")


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
            db_path = str(get_vibe3_db_path(git_dir))
            git_dir.joinpath("vibe3").mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._init_db()
        logger.bind(external="sqlite", operation="init", db_path=db_path).debug(
            "SQLite client initialized"
        )

    @classmethod
    def from_repo_path(cls: type[T], repo_path: Path) -> T:
        """Create a SQLiteClient resolved from a repository root path.

        Centralizes the handoff.db path resolution to avoid duplication
        across worktree environment modules.

        Args:
            repo_path: Path to the main repository root

        Returns:
            New SQLiteClient instance with the resolved db path
        """
        git_dir = repo_path / ".git"
        db_path = str(get_vibe3_db_path(git_dir))
        return cls(db_path=db_path)

    def _init_db(self) -> None:
        """Initialize schema and run migrations (idempotent).

        Uses a migration version check to avoid re-running full DDL
        on every SQLiteClient instantiation. Increments migration_version
        in sqlite_schema.py when adding new migrations.
        """
        conn = _get_global_connection(self.db_path)
        with _global_lock:
            # Lightweight guard: check migration version
            # Update required_migration_version when adding new migrations
            required_migration_version = 3  # Increment when adding

            try:
                version_row = conn.execute(
                    "SELECT value FROM schema_meta WHERE key = 'migration_version'"
                ).fetchone()
                current_version = int(version_row[0]) if version_row else 0
                if current_version >= required_migration_version:
                    # Migrations already applied, skip full init
                    return
            except (sqlite3.OperationalError, ValueError):
                # Table doesn't exist or invalid version, need to init
                pass

            # Run full schema initialization (includes migration_version update)
            init_schema(conn)

    def _get_connection(self) -> sqlite3.Connection:
        """Get the global singleton connection for this database."""
        return _get_global_connection(self.db_path)
