# Database Migration: Error Severity System

**Date**: 2026-05-22
**Issue**: Missing `severity` column in `error_log` table
**PR**: #1216 (error severity system)

## Problem

PR #1216 introduced `severity` field to `error_log` table, but existing databases
may skip migration if they already have `migration_version=1` in `schema_meta`.

## Impact

- `record_error()` calls fail with "table error_log has no column named severity"
- `vibe serve status` shows "No errors recorded" even when errors occur

## Solution

Run migration manually for existing databases:

V3 uses a single `handoff.db` database stored under the git common directory,
which is shared across all worktrees.

```python
import subprocess
import sqlite3
from vibe3.clients.sqlite_schema import init_schema

# Get the shared database path (worktree-aware)
git_common_dir = subprocess.check_output(
    ["git", "rev-parse", "--git-common-dir"], text=True
).strip()
db_path = f"{git_common_dir}/vibe3/handoff.db"

conn = sqlite3.connect(db_path)
init_schema(conn)
```

## Verification

```bash
# Set database path (worktree-aware)
DB_PATH="$(git rev-parse --git-common-dir)/vibe3/handoff.db"

# Check error_log schema
sqlite3 "$DB_PATH" "PRAGMA table_info(error_log)"

# Should include severity field:
# 7|severity|TEXT|0||0

# Check migration version
sqlite3 "$DB_PATH" "SELECT * FROM schema_meta"

# Should include:
# migration_version|1
```

## Prevention

For future migrations that add new columns:
1. Increment `required_migration_version` in `sqlite_base.py`
2. Increment `migration_version` in `sqlite_schema.py`
3. Test migration on existing database before merging
