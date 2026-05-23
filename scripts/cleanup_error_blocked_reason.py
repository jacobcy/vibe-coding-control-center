#!/usr/bin/env python3
"""Clean up historical blocked_reason data containing error messages.

This script addresses historical data where runtime errors were incorrectly
written to blocked_reason instead of error_log. After Phase 1-3 refactoring,
blocked_reason should only contain business logic reasons.

Usage:
    uv run python scripts/cleanup_error_blocked_reason.py --dry-run
    uv run python scripts/cleanup_error_blocked_reason.py --execute
"""

import argparse
import sqlite3
import subprocess
from pathlib import Path

ERROR_PATTERNS = [
    "no such column",
    "codeagent-wrapper failed",
    "claude completed without agent_message",
    "Backend completed but produced no output",
    "E_EXEC_NO_OUTPUT",
    "Failed to resolve permanent worktree",
    "[worktree_unavailable]",
    "[launch_failed]",
    "Tmux session",
    "already exists",
    "Health check failed",
]


def get_default_db_path() -> str:
    """Get default database path using git common dir.

    In linked worktrees, .git is a file not a directory.
    Use git rev-parse --git-common-dir to find the shared db location.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_common_dir = result.stdout.strip()
        if git_common_dir:
            return str(Path(git_common_dir) / "vibe3" / "handoff.db")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    # Fallback for non-worktree scenarios
    return ".git/vibe3/handoff.db"


def find_error_blocked_reasons(db_path: str) -> list[dict]:
    """Find blocked_reason entries containing error messages.

    Uses parameterized queries to avoid SQL injection issues.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build parameterized query: blocked_reason LIKE ? OR blocked_reason LIKE ? ...
    placeholders = " OR ".join(["blocked_reason LIKE ?"] * len(ERROR_PATTERNS))
    params = [f"%{p}%" for p in ERROR_PATTERNS]

    query = f"""
        SELECT branch, blocked_reason, flow_status
        FROM flow_state
        WHERE blocked_reason IS NOT NULL
        AND ({placeholders})
    """

    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def cleanup_error_blocked_reasons(db_path: str, dry_run: bool = True) -> int:
    """Clear blocked_reason for entries containing error messages.

    Note: We do NOT change flow_status. Per Copilot review, 'failed' is not
    a valid flow_status value (valid: active, blocked, done, stale, aborted).
    Runtime failure semantics are tracked via error_log, not flow_status.

    Returns count of records that would be/were updated.
    """
    rows = find_error_blocked_reasons(db_path)

    if dry_run:
        print(f"[DRY RUN] Would clear blocked_reason for {len(rows)} records:\n")
        for row in rows:
            reason = row["blocked_reason"] or ""
            print(f"  - {row['branch']}: {reason[:80]}...")
        return len(rows)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Build parameterized query
    placeholders = " OR ".join(["blocked_reason LIKE ?"] * len(ERROR_PATTERNS))
    params = [f"%{p}%" for p in ERROR_PATTERNS]

    query = f"""
        UPDATE flow_state
        SET blocked_reason = NULL
        WHERE blocked_reason IS NOT NULL
        AND ({placeholders})
    """

    cursor.execute(query, params)
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    print(f"Cleared blocked_reason for {affected} records")
    return affected


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up error messages in blocked_reason"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--dry-run", action="store_true", help="Show what would be cleaned"
    )
    group.add_argument(
        "--execute", action="store_true", help="Actually clean the data"
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Database path (default: auto-detect from git common dir)",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path) if args.db_path else Path(get_default_db_path())
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    cleanup_error_blocked_reasons(str(db_path), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    exit(main())
