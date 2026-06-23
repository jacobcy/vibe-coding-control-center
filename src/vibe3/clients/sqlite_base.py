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

# Per-thread connections to avoid concurrent query corruption
# Each thread gets its own connection; tracked for bulk close in tests/atexit.
# Assumes bounded thread pools (ThreadPoolExecutor). Dynamic thread creation
# may orphan connections until process exit when atexit runs cleanup.
_thread_local = threading.local()
_thread_conns: set[sqlite3.Connection] = set()
_thread_conns_lock = threading.Lock()
_init_done: set[str] = set()  # tracks db_path values already initialized
_init_lock = threading.Lock()


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


def _get_thread_connection(db_path: str) -> sqlite3.Connection:
    """Get or create a thread-local database connection.

    Uses per-thread connections to avoid concurrent query corruption.
    Each thread gets its own connection, preventing race conditions
    where multiple threads mutate shared connection state (cursor/row_factory).

    Thread-safe: Uses threading.local() for per-thread storage.
    Connection count bounded by thread count, not operation count.
    """
    conn = getattr(_thread_local, "conn", None)
    thread_db_path = getattr(_thread_local, "db_path", None)

    if conn is None or thread_db_path != db_path or not _is_connection_usable(conn):
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")  # ensure WAL on each new connection
        _thread_local.conn = conn
        _thread_local.db_path = db_path

        with _thread_conns_lock:
            _thread_conns.add(conn)

    return conn


def _close_all_connections() -> None:
    """Close all tracked thread-local connections.

    Used for test isolation and atexit cleanup.
    Closes current thread's connection and all tracked connections.
    """
    # Close current thread's connection and remove from tracked set
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _thread_local.conn = None

    # Close all remaining tracked connections (for test cleanup / atexit)
    with _thread_conns_lock:
        for c in list(_thread_conns):
            try:
                c.close()
            except Exception:
                pass
        _thread_conns.clear()


def _utcnow_iso() -> str:
    """Return current UTC timestamp in ISO format.

    This helper ensures consistent timezone usage across all SQLite
    repository timestamp operations.
    """
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


atexit.register(_close_all_connections)


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

        Note: init_schema() must remain idempotent — multiple threads may
        race to the same code path before _init_done is populated.
        """
        with _init_lock:
            # Lightweight guard: check migration version
            # Update required_migration_version when adding new migrations
            required_migration_version = 5  # Increment when adding

            # Check if already initialized for this db_path
            if self.db_path in _init_done:
                return

            conn = _get_thread_connection(self.db_path)

            try:
                version_row = conn.execute(
                    "SELECT value FROM schema_meta WHERE key = 'migration_version'"
                ).fetchone()
                current_version = int(version_row[0]) if version_row else 0
                if current_version >= required_migration_version:
                    # Migrations already applied, skip full init
                    _init_done.add(self.db_path)
                    return
            except (sqlite3.OperationalError, ValueError):
                # Table doesn't exist or invalid version, need to init
                pass

            # Run full schema initialization (includes migration_version update)
            init_schema(conn)
            _init_done.add(self.db_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get the thread-local connection for this database."""
        return _get_thread_connection(self.db_path)
