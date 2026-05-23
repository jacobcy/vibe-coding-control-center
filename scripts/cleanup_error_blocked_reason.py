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


def find_error_blocked_reasons(db_path: str) -> list[dict]:
    """Find blocked_reason entries containing error messages."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    where_clauses = " OR ".join(
        [f"blocked_reason LIKE '%{p}%'" for p in ERROR_PATTERNS]
    )
    query = f"""
        SELECT branch, blocked_reason, flow_status
        FROM flow_state
        WHERE blocked_reason IS NOT NULL
        AND ({where_clauses})
    """

    cursor.execute(query)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def cleanup_error_blocked_reasons(db_path: str, dry_run: bool = True) -> int:
    """Clear blocked_reason for entries containing error messages.

    Returns count of records that would be/were updated.
    """
    rows = find_error_blocked_reasons(db_path)

    if dry_run:
        print(f"[DRY RUN] Would clear blocked_reason for {len(rows)} records:\n")
        for row in rows:
            print(f"  - {row['branch']}: {row['blocked_reason'][:80]}...")
        return len(rows)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    where_clauses = " OR ".join(
        [f"blocked_reason LIKE '%{p}%'" for p in ERROR_PATTERNS]
    )
    query = f"""
        UPDATE flow_state
        SET blocked_reason = NULL,
            flow_status = 'failed'
        WHERE blocked_reason IS NOT NULL
        AND ({where_clauses})
    """

    cursor.execute(query)
    affected = cursor.rowcount
    conn.commit()
    conn.close()

    print(
        f"Cleared blocked_reason for {affected} records "
        "(set flow_status to 'failed')"
    )
    return affected


def main():
    parser = argparse.ArgumentParser(
        description="Clean up error messages in blocked_reason"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be cleaned"
    )
    parser.add_argument(
        "--execute", action="store_true", help="Actually clean the data"
    )
    parser.add_argument(
        "--db-path",
        default=".git/vibe3/handoff.db",
        help="Database path",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    if args.execute:
        cleanup_error_blocked_reasons(str(db_path), dry_run=False)
    else:
        cleanup_error_blocked_reasons(str(db_path), dry_run=True)

    return 0


if __name__ == "__main__":
    exit(main())
