"""SQLite schema definitions and migration helpers."""

import sqlite3

from loguru import logger

# DDL statements
_CREATE_SCHEMA_META = """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
"""

_CREATE_FLOW_STATE = """
    CREATE TABLE IF NOT EXISTS flow_state (
        branch TEXT PRIMARY KEY,
        flow_slug TEXT NOT NULL,
        spec_ref TEXT,
        plan_ref TEXT,
        report_ref TEXT,
        audit_ref TEXT,
        pr_ref TEXT,
        planner_actor TEXT,
        executor_actor TEXT,
        reviewer_actor TEXT,
        latest_actor TEXT,
        initiated_by TEXT,
        blocked_by TEXT,
        next_step TEXT,
        flow_status TEXT NOT NULL DEFAULT 'active',
        updated_at TEXT NOT NULL,
        project_item_id TEXT,
        project_node_id TEXT,
        planner_status TEXT,
        executor_status TEXT,
        reviewer_status TEXT,
        execution_pid INTEGER,
        execution_started_at TEXT,
        execution_completed_at TEXT
    )
"""

_CREATE_FLOW_ISSUE_LINKS = """
    CREATE TABLE IF NOT EXISTS flow_issue_links (
        branch TEXT NOT NULL,
        issue_number INTEGER NOT NULL,
        issue_role TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (branch, issue_number, issue_role)
    )
"""

_CREATE_TASK_ISSUE_INDEX = """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_single_task_issue
    ON flow_issue_links(branch)
    WHERE issue_role = 'task'
"""

_CREATE_FLOW_EVENTS = """
    CREATE TABLE IF NOT EXISTS flow_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch TEXT NOT NULL,
        event_type TEXT NOT NULL,
        actor TEXT NOT NULL,
        detail TEXT,
        refs TEXT,
        created_at TEXT NOT NULL
    )
"""


_CREATE_RUNTIME_SESSION = """
    CREATE TABLE IF NOT EXISTS runtime_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT NOT NULL,
        branch TEXT NOT NULL,
        session_name TEXT NOT NULL,
        backend_session_id TEXT,
        tmux_session TEXT,
        log_path TEXT,
        status TEXT NOT NULL DEFAULT 'starting',
        started_at TEXT,
        ended_at TEXT,
        worktree_path TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
"""

_CREATE_RUNTIME_SESSION_INDEXES = """
    CREATE INDEX IF NOT EXISTS idx_runtime_session_status_role
        ON runtime_session(status, role);

    CREATE INDEX IF NOT EXISTS idx_runtime_session_branch_role
        ON runtime_session(branch, role);

    CREATE INDEX IF NOT EXISTS idx_runtime_session_role_branch_target
        ON runtime_session(role, branch, target_id)
"""

_CREATE_FLOW_CONTEXT_CACHE = """
    CREATE TABLE IF NOT EXISTS flow_context_cache (
        branch TEXT PRIMARY KEY,
        task_issue_number INTEGER,
        issue_title TEXT,
        pr_number INTEGER,
        pr_title TEXT,
        updated_at TEXT NOT NULL
    )
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and run migrations."""
    # Enable WAL mode so concurrent readers (CLI, orchestra, tmux agents)
    # never block each other.  In DELETE journal mode (the default), a writer
    # holds an exclusive lock that can cause CLI reads to see stale or
    # incomplete data during multi-process access.
    conn.execute("PRAGMA journal_mode=WAL")

    cursor = conn.cursor()

    cursor.execute(_CREATE_SCHEMA_META)
    cursor.execute(_CREATE_FLOW_STATE)

    # Migration: add bridge columns if missing (idempotent)
    existing = {
        row[1] for row in cursor.execute("PRAGMA table_info(flow_state)").fetchall()
    }
    # Safe to use f-string: col values are hardcoded in the loop below
    for col in ("project_item_id", "project_node_id"):
        if col not in existing:
            cursor.execute(f"ALTER TABLE flow_state ADD COLUMN {col} TEXT")
            logger.bind(external="sqlite", operation="migration").info(
                f"Added {col} column to flow_state"
            )

    # Migration: add initiated_by column if missing
    if "initiated_by" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN initiated_by TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added initiated_by column to flow_state"
        )

    # Migration: add async execution tracking columns if missing
    async_columns = {
        "planner_status": "TEXT",
        "executor_status": "TEXT",
        "reviewer_status": "TEXT",
        "execution_pid": "INTEGER",
        "execution_started_at": "TEXT",
        "execution_completed_at": "TEXT",
    }
    for col, col_type in async_columns.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE flow_state ADD COLUMN {col} {col_type}")
            logger.bind(external="sqlite", operation="migration").info(
                f"Added {col} column to flow_state"
            )

    # Migration: add pr_ref column if missing
    if "pr_ref" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN pr_ref TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added pr_ref column to flow_state"
        )

    # Migration: split blocked_by into blocked_by_issue (INT) +
    # blocked_reason (TEXT). This resolves semantic confusion:
    # blocked_by currently mixes issue numbers and reason text.
    if "blocked_by_issue" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN blocked_by_issue INTEGER")
        logger.bind(external="sqlite", operation="migration").info(
            "Added blocked_by_issue column to flow_state"
        )

    if "blocked_reason" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN blocked_reason TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added blocked_reason column to flow_state"
        )

    # Migration: add failed_reason field for fail_flow() support
    if "failed_reason" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN failed_reason TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added failed_reason column to flow_state"
        )

    # Migration: add latest_verdict field for verdict tracking
    if "latest_verdict" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN latest_verdict TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added latest_verdict column to flow_state"
        )

    # Migration: migrate existing blocked_by data to new fields
    # Pattern: "#218" → blocked_by_issue=218, other text → blocked_reason
    if "blocked_by" in existing and (
        "blocked_by_issue" not in existing or "blocked_reason" not in existing
    ):
        # Parse blocked_by values and migrate
        cursor.execute("""
            UPDATE flow_state
            SET
                blocked_by_issue = CASE
                    WHEN blocked_by LIKE '#%' THEN
                        CAST(substr(blocked_by, 2) AS INTEGER)
                    ELSE NULL
                END,
                blocked_reason = CASE
                    WHEN blocked_by LIKE '#%' THEN NULL
                    ELSE blocked_by
                END
            WHERE blocked_by IS NOT NULL
        """)
        logger.bind(external="sqlite", operation="migration").info(
            "Migrated blocked_by data to blocked_by_issue and blocked_reason fields"
        )

    cursor.execute(_CREATE_FLOW_ISSUE_LINKS)
    cursor.execute(_CREATE_TASK_ISSUE_INDEX)
    cursor.execute(_CREATE_FLOW_EVENTS)
    cursor.execute(_CREATE_RUNTIME_SESSION)
    cursor.execute(_CREATE_FLOW_CONTEXT_CACHE)

    # Create indexes for runtime_session table
    for stmt in _CREATE_RUNTIME_SESSION_INDEXES.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cursor.execute(stmt)

    # Migration: add refs column to flow_events if missing
    event_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(flow_events)").fetchall()
    }
    if "refs" not in event_columns:
        cursor.execute("ALTER TABLE flow_events ADD COLUMN refs TEXT")

    # Normalize legacy issue_role values from the old classification view.
    cursor.execute(
        "UPDATE flow_issue_links SET issue_role = 'related' WHERE issue_role = 'repo'"
    )

    # Migration: Backfill task_issue_number to flow_issue_links if legacy column exists
    if "task_issue_number" in existing:
        before_changes = conn.total_changes
        cursor.execute("""
            INSERT OR IGNORE INTO flow_issue_links
                (branch, issue_number, issue_role, created_at)
            SELECT branch, task_issue_number, 'task', datetime('now')
            FROM flow_state
            WHERE task_issue_number IS NOT NULL
            """)
        inserted = conn.total_changes - before_changes
        if inserted:
            logger.bind(external="sqlite", operation="migration").debug(
                "Backfilled task_issue_number from flow_state to flow_issue_links",
                inserted=inserted,
            )

    cursor.execute(
        "INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', 'v3')"
    )
    cursor.execute(
        "INSERT OR IGNORE INTO schema_meta (key, value) "
        "VALUES ('store_type', 'handoff_store')"
    )
    conn.commit()
    logger.bind(external="sqlite", operation="init_schema").debug(
        "Database schema initialized"
    )
