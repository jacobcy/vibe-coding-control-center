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
        task_issue_number INTEGER,
        pr_number INTEGER,
        spec_ref TEXT,
        plan_ref TEXT,
        report_ref TEXT,
        audit_ref TEXT,
        planner_actor TEXT,
        planner_session_id TEXT,
        executor_actor TEXT,
        executor_session_id TEXT,
        reviewer_actor TEXT,
        reviewer_session_id TEXT,
        latest_actor TEXT,
        blocked_by TEXT,
        next_step TEXT,
        flow_status TEXT NOT NULL DEFAULT 'active',
        updated_at TEXT NOT NULL,
        project_item_id TEXT,
        project_node_id TEXT
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
        created_at TEXT NOT NULL
    )
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and run migrations."""
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

    cursor.execute(_CREATE_FLOW_ISSUE_LINKS)
    cursor.execute(_CREATE_TASK_ISSUE_INDEX)
    cursor.execute(_CREATE_FLOW_EVENTS)

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
