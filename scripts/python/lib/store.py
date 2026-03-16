import datetime
import os
import sqlite3


class Vibe3Store:
    def __init__(self, db_path=None):
        if db_path is None:
            # Use git rev-parse --git-dir to find the correct directory for the database
            git_dir = os.popen("git rev-parse --git-dir").read().strip()
            vibe3_dir = os.path.join(git_dir, "vibe3")
            if not os.path.exists(vibe3_dir):
                os.makedirs(vibe3_dir, exist_ok=True)
            db_path = os.path.join(vibe3_dir, "handoff.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. schema_meta
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # 2. flow_state
            cursor.execute("""
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
                    updated_at TEXT NOT NULL
                )
            """)

            # 3. flow_issue_links
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flow_issue_links (
                    branch TEXT NOT NULL,
                    issue_number INTEGER NOT NULL,
                    issue_role TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (branch, issue_number, issue_role)
                )
            """)

            # Unique index for task issue as per standard
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_single_task_issue
                ON flow_issue_links(branch)
                WHERE issue_role = 'task'
            """)

            # 4. flow_events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flow_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    branch TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Set schema version if not set
            cursor.execute(
                "INSERT OR IGNORE INTO schema_meta (key, value) "
                "VALUES ('schema_version', 'v3')"
            )
            cursor.execute(
                "INSERT OR IGNORE INTO schema_meta (key, value) "
                "VALUES ('store_type', 'handoff_store')"
            )
            conn.commit()

    def get_flow_state(self, branch):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state WHERE branch = ?", (branch,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_flow_state(self, branch, **kwargs):
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.datetime.now().isoformat()

        fields = list(kwargs.keys())
        values = [kwargs[f] for f in fields]

        set_clause = ", ".join([f"{f} = ?" for f in fields])

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Ensure the row exists
            cursor.execute(
                "INSERT OR IGNORE INTO flow_state (branch, flow_slug, updated_at) "
                "VALUES (?, ?, ?)",
                (branch, kwargs.get("flow_slug", "unknown"), kwargs["updated_at"]),
            )

            query = f"UPDATE flow_state SET {set_clause} WHERE branch = ?"
            cursor.execute(query, values + [branch])
            conn.commit()

    def add_event(self, branch, event_type, actor, detail=None):
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO flow_events (branch, event_type, actor, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (branch, event_type, actor, detail, now),
            )
            conn.commit()

    def add_issue_link(self, branch, issue_number, role):
        now = datetime.datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO flow_issue_links
                    (branch, issue_number, issue_role, created_at)
                VALUES (?, ?, ?, ?)
            """,
                (branch, issue_number, role, now),
            )
            conn.commit()

    def get_issue_links(self, branch):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_issue_links WHERE branch = ?", (branch,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_flows(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state WHERE flow_status = 'active'")
            return [dict(row) for row in cursor.fetchall()]

    def get_all_flows(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flow_state")
            return [dict(row) for row in cursor.fetchall()]
