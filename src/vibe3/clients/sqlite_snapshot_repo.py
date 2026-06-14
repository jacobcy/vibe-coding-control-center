"""SQLite repository methods for snapshot registry persistence."""

from loguru import logger

from vibe3.clients.sqlite_base import _HasConnection


class SQLiteSnapshotRepo(_HasConnection):
    """Snapshot registry read/write operations."""

    db_path: str

    def upsert_snapshot_registry(
        self,
        snapshot_id: str,
        branch: str,
        commit_short: str,
        commit_hash: str | None,
        created_at: str,
        file_path: str,
    ) -> None:
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO snapshot_registry "
                "(snapshot_id, branch, commit_short, commit_hash, "
                "created_at, file_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (snapshot_id, branch, commit_short, commit_hash, created_at, file_path),
            )
        logger.bind(
            external="sqlite",
            operation="upsert_snapshot_registry",
            snapshot_id=snapshot_id,
        ).debug("Snapshot registered")

    def find_snapshots_by_branch(
        self, branch: str, limit: int = 20
    ) -> list[dict[str, str]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        # Match both normalized and origin/ prefixed branch names
        cursor.execute(
            "SELECT snapshot_id, branch, commit_hash, commit_short, "
            "created_at, file_path FROM snapshot_registry "
            "WHERE branch = ? OR branch = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (branch, branch.removeprefix("origin/"), limit),
        )
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def list_snapshots_from_db(
        self, include_baselines: bool = False, limit: int | None = 50
    ) -> list[str]:
        """List snapshot IDs ordered by creation time (newest first)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT snapshot_id FROM snapshot_registry ORDER BY created_at DESC"
        params: list = []
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        cursor.execute(query, params)
        return [row[0] for row in cursor.fetchall()]
