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
        indicate_ref TEXT,
        pr_ref TEXT,
        planner_actor TEXT,
        executor_actor TEXT,
        reviewer_actor TEXT,
        manager_actor TEXT,
        latest_actor TEXT,
        initiated_by TEXT,
        blocked_by TEXT,
        next_step TEXT,
        flow_status TEXT NOT NULL DEFAULT 'active',
        updated_at TEXT NOT NULL,
        planner_status TEXT,
        executor_status TEXT,
        reviewer_status TEXT,
        execution_pid INTEGER,
        execution_started_at TEXT,
        execution_completed_at TEXT,
        transition_count INTEGER DEFAULT 0
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

_CREATE_ERROR_LOG = """
    CREATE TABLE IF NOT EXISTS error_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tick_id INTEGER NOT NULL,
        error_code TEXT NOT NULL,
        error_message TEXT NOT NULL,
        severity TEXT,
        issue_number INTEGER,
        branch TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""

_CREATE_ERROR_LOG_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_error_log_tick ON error_log(tick_id)",
    "CREATE INDEX IF NOT EXISTS idx_error_log_code ON error_log(error_code)",
    "CREATE INDEX IF NOT EXISTS idx_error_log_created ON error_log(created_at)",
    (
        "CREATE INDEX IF NOT EXISTS idx_error_log_issue_created ON "
        "error_log(issue_number, created_at DESC)"
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_error_log_branch_created ON "
        "error_log(branch, created_at DESC)"
    ),
]

# Severity index created separately after migration
_CREATE_ERROR_SEVERITY_INDEX = (
    "CREATE INDEX IF NOT EXISTS idx_error_severity ON error_log(severity)"
)

_CREATE_FAILED_GATE_STATE = """
    CREATE TABLE IF NOT EXISTS failed_gate_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        is_active INTEGER NOT NULL DEFAULT 0,
        reason TEXT,
        triggered_at TEXT,
        triggered_by_error_code TEXT,
        cleared_at TEXT,
        cleared_by TEXT,
        cleared_reason TEXT,
        blocked_ticks INTEGER NOT NULL DEFAULT 0
    )
"""

_CREATE_ORCHESTRA_QUEUE = """
    CREATE TABLE IF NOT EXISTS orchestra_queue (
        issue_number INTEGER PRIMARY KEY,
        collected_state TEXT,
        waiting_state TEXT,
        updated_at TEXT NOT NULL
    )
"""

_CREATE_SNAPSHOT_REGISTRY = """
    CREATE TABLE IF NOT EXISTS snapshot_registry (
        snapshot_id TEXT PRIMARY KEY,
        branch TEXT NOT NULL,
        commit_short TEXT NOT NULL,
        commit_hash TEXT,
        created_at TEXT NOT NULL,
        file_path TEXT NOT NULL
    )
"""

_CREATE_SNAPSHOT_REGISTRY_INDEXES = """
    CREATE INDEX IF NOT EXISTS idx_snapshot_registry_branch
        ON snapshot_registry(branch, created_at DESC)
"""

_CREATE_TRANSITION_HISTORY = """
    CREATE TABLE IF NOT EXISTS transition_history (
        branch TEXT NOT NULL,
        from_state TEXT NOT NULL,
        to_state TEXT NOT NULL,
        created_at TEXT NOT NULL,
        actor TEXT,
        event_id INTEGER REFERENCES flow_events(id)
    )
"""

_CREATE_TRANSITION_HISTORY_INDEXES = """
    CREATE INDEX IF NOT EXISTS idx_transition_pair
    ON transition_history(branch, from_state, to_state);

    CREATE INDEX IF NOT EXISTS idx_transition_branch_time
    ON transition_history(branch, created_at DESC)
"""


_CLEAN_STALE_VERDICT_LINES_SQL = """
    UPDATE flow_events
    SET detail = CASE
        WHEN instr(detail, char(10)) > 0
            THEN substr(detail, instr(detail, char(10)) + 1)
        ELSE REPLACE(detail, 'verdict: UNKNOWN', '')
    END
    WHERE event_type IN ('handoff_plan', 'handoff_report', 'handoff_run')
      AND detail LIKE 'verdict: UNKNOWN%'
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

    # Migration: add initiated_by column if missing
    existing = {
        row[1] for row in cursor.execute("PRAGMA table_info(flow_state)").fetchall()
    }
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

    if "blocked_reason_summary" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN blocked_reason_summary TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added blocked_reason_summary column to flow_state"
        )

    # Migration: add latest_verdict field for verdict tracking
    if "latest_verdict" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN latest_verdict TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added latest_verdict column to flow_state"
        )

    # Migration: add deleted_at field for soft delete support
    if "deleted_at" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN deleted_at TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added deleted_at column to flow_state"
        )

    # Migration: add worktree_path field for canonical worktree tracking
    if "worktree_path" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN worktree_path TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added worktree_path column to flow_state"
        )

    # Migration: add transition_count field for L3 no-op gate protection
    if "transition_count" not in existing:
        cursor.execute(
            "ALTER TABLE flow_state ADD COLUMN transition_count INTEGER DEFAULT 0"
        )
        logger.bind(external="sqlite", operation="migration").info(
            "Added transition_count column to flow_state"
        )

    # Migration: add retry counter fields for no-op gate GitHub API failures
    retry_columns = {
        "noop_gate_github_retry_count": "INTEGER DEFAULT 0",
        "noop_gate_malformed_retry_count": "INTEGER DEFAULT 0",
    }
    for col, col_type in retry_columns.items():
        if col not in existing:
            cursor.execute(f"ALTER TABLE flow_state ADD COLUMN {col} {col_type}")
            logger.bind(external="sqlite", operation="migration").info(
                f"Added {col} column to flow_state"
            )

    # Migration: add indicate_ref column for indicate handoff tracking
    if "indicate_ref" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN indicate_ref TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added indicate_ref column to flow_state"
        )

    # Migration: add manager_actor column for manager role tracking
    if "manager_actor" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN manager_actor TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added manager_actor column to flow_state"
        )

    # Migration: add creation_source column for static branch creation tracking
    if "creation_source" not in existing:
        cursor.execute("ALTER TABLE flow_state ADD COLUMN creation_source TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added creation_source column to flow_state"
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
    cursor.execute(_CREATE_ERROR_LOG)
    for index_sql in _CREATE_ERROR_LOG_INDEXES:
        cursor.execute(index_sql)

    # Migration: add severity column to error_log and backfill from registry
    error_log_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(error_log)").fetchall()
    }
    if "severity" not in error_log_columns:
        cursor.execute("ALTER TABLE error_log ADD COLUMN severity TEXT")
        logger.bind(external="sqlite", operation="migration").info(
            "Added severity column to error_log"
        )

    # Backfill NULL/missing severity values using registry
    # Runs both for newly added column and for any rows with NULL severity
    # (handles interrupted migrations or earlier code writing without severity)

    before_changes = conn.total_changes
    # Fetch all error codes with NULL severity
    null_severity_codes = cursor.execute(
        "SELECT DISTINCT error_code FROM error_log WHERE severity IS NULL"
    ).fetchall()
    for (error_code,) in null_severity_codes:
        # Inline severity inference based on error code prefix
        # Avoids importing get_error_handling_contract from vibe3.exceptions
        _severity_prefix_map: dict[str, str] = {
            "E_MODEL_": "WARNING",
            "E_API_": "ERROR",
            "E_EXEC_": "WARNING",
            "E_CAPACITY_": "WARNING",
            "E_DISPATCH_": "ERROR",
            "E_CONFIG_": "ERROR",
            "E_INVALID_": "ERROR",
            "E_ISSUE_": "ERROR",
        }
        severity = "ERROR"  # Conservative fallback
        for prefix, sev in _severity_prefix_map.items():
            if error_code.startswith(prefix):
                severity = sev
                break
        cursor.execute(
            "UPDATE error_log SET severity = ? WHERE error_code = ? "
            "AND severity IS NULL",
            (severity, error_code),
        )
    updated = conn.total_changes - before_changes
    # Only log if updated is a real number (not a mock in tests)
    if isinstance(updated, int) and updated > 0:
        logger.bind(external="sqlite", operation="migration").info(
            f"Backfilled severity for {updated} error_log records"
        )

    # Create severity index (after column exists)
    cursor.execute(_CREATE_ERROR_SEVERITY_INDEX)

    cursor.execute(_CREATE_FAILED_GATE_STATE)
    cursor.execute(_CREATE_ORCHESTRA_QUEUE)
    cursor.execute(_CREATE_SNAPSHOT_REGISTRY)
    for stmt in _CREATE_SNAPSHOT_REGISTRY_INDEXES.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cursor.execute(stmt)

    # Migration: add baseline_for column to snapshot_registry
    registry_columns = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(snapshot_registry)").fetchall()
    }
    if "baseline_for" not in registry_columns:
        cursor.execute("ALTER TABLE snapshot_registry ADD COLUMN baseline_for TEXT")

    cursor.execute(_CREATE_TRANSITION_HISTORY)
    for stmt in _CREATE_TRANSITION_HISTORY_INDEXES.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cursor.execute(stmt)

    # Migration: add refs column to flow_events (before transition_history migration)
    event_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(flow_events)").fetchall()
    }
    if "refs" not in event_columns:
        cursor.execute("ALTER TABLE flow_events ADD COLUMN refs TEXT")

    # Migration: populate transition_history from existing flow_events
    # Check if transition_history already has data (avoid re-migration)
    existing_transitions = cursor.execute(
        "SELECT COUNT(*) FROM transition_history"
    ).fetchone()[0]

    if existing_transitions == 0:
        # Migrate historical state_transitioned events from flow_events.refs JSON
        before_changes = conn.total_changes
        cursor.execute("""
            INSERT INTO transition_history
                (branch, from_state, to_state, created_at, actor, event_id)
            SELECT
                branch,
                json_extract(refs, '$.before_state') as from_state,
                json_extract(refs, '$.after_state') as to_state,
                created_at,
                actor,
                id as event_id
            FROM flow_events
            WHERE event_type = 'state_transitioned'
              AND refs IS NOT NULL
              AND json_valid(refs)
              AND json_extract(refs, '$.before_state') IS NOT NULL
              AND json_extract(refs, '$.after_state') IS NOT NULL
        """)

        migrated = conn.total_changes - before_changes
        if migrated > 0:
            logger.bind(external="sqlite", operation="migration").info(
                f"Migrated {migrated} historical transitions from "
                "flow_events to transition_history"
            )

    # Migration: remove retry_count, last_attempted_at, enqueued_at from orchestra_queue
    # (SQLite doesn't support DROP COLUMN, so recreate table)
    queue_columns = {
        row[1]
        for row in cursor.execute("PRAGMA table_info(orchestra_queue)").fetchall()
    }
    legacy_cols = {"retry_count", "last_attempted_at", "enqueued_at"}
    if legacy_cols & queue_columns:
        cursor.execute("""
            CREATE TABLE orchestra_queue_new (
                issue_number INTEGER PRIMARY KEY,
                collected_state TEXT,
                waiting_state TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            INSERT INTO orchestra_queue_new
            SELECT issue_number, collected_state, waiting_state, updated_at
            FROM orchestra_queue
        """)
        cursor.execute("DROP TABLE orchestra_queue")
        cursor.execute("ALTER TABLE orchestra_queue_new RENAME TO orchestra_queue")
        removed = sorted(legacy_cols & queue_columns)
        logger.bind(external="sqlite", operation="migration").info(
            f"Removed legacy columns from orchestra_queue: {', '.join(removed)}"
        )

    # Create indexes for runtime_session table
    for stmt in _CREATE_RUNTIME_SESSION_INDEXES.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            cursor.execute(stmt)

    before_changes = conn.total_changes
    cursor.execute(_CLEAN_STALE_VERDICT_LINES_SQL)
    cleaned = conn.total_changes - before_changes
    if cleaned:
        logger.bind(external="sqlite", operation="migration").info(
            f"Cleaned stale plan/run verdict lines from {cleaned} flow_events rows"
        )

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
    # Track migration version for lightweight guard in sqlite_base.py
    # Increment this when adding new migrations that need to run on existing DBs
    cursor.execute(
        "INSERT OR REPLACE INTO schema_meta (key, value) "
        "VALUES ('migration_version', '4')"
    )
    conn.commit()
    logger.bind(external="sqlite", operation="init_schema").debug(
        "Database schema initialized"
    )
