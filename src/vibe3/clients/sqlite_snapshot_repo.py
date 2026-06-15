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
        baseline_for: str | None = None,
    ) -> None:
        conn = self._get_connection()
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO snapshot_registry "
                "(snapshot_id, branch, commit_short, commit_hash, "
                "created_at, file_path, baseline_for) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    snapshot_id,
                    branch,
                    commit_short,
                    commit_hash,
                    created_at,
                    file_path,
                    baseline_for,
                ),
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

    def find_baseline(self, branch: str) -> dict | None:
        """Return the baseline registry row for a branch, or None."""
        cursor = self._get_connection().cursor()
        cursor.execute(
            "SELECT * FROM snapshot_registry WHERE baseline_for = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (branch,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))
