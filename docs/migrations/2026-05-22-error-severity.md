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

```python
import sqlite3
from vibe3.clients.sqlite_schema import init_schema

# Migrate all databases
for db_name in ['vibe.db', 'handoff.db']:
    db_path = f'/path/to/.git/vibe3/{db_name}'
    conn = sqlite3.connect(db_path)
    init_schema(conn)
```

## Verification

```bash
# Check error_log schema
sqlite3 .git/vibe3/vibe.db "PRAGMA table_info(error_log)"

# Should include severity field:
# 7|severity|TEXT|0||0

# Check migration version
sqlite3 .git/vibe3/vibe.db "SELECT * FROM schema_meta"

# Should include:
# migration_version|1
```

## Prevention

For future migrations that add new columns:
1. Increment `required_migration_version` in `sqlite_base.py`
2. Increment `migration_version` in `sqlite_schema.py`
3. Test migration on existing database before merging
