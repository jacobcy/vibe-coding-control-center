"""Shared SQLite client bootstrap and connection helpers."""

import sqlite3
from pathlib import Path

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.exceptions import GitError


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
        with sqlite3.connect(self.db_path) as conn:
            init_schema(conn)
