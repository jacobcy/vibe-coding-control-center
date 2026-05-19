# Tombstone Normalization Architecture

## Overview

Soft-deleted flow_state records are normalized to tombstone state to prevent contradictory metadata where deleted flows still appear active.

## Problem

Before tombstone normalization, `soft_delete_flow()` only set `deleted_at` timestamp, leaving:
- `flow_status='active'`
- refs (spec_ref, plan_ref, report_ref, audit_ref, indicate_ref, pr_ref) populated
- reasons (blocked_reason, failed_reason, blocked_by_issue) populated
- worktree_path populated
- actor fields populated

This created architectural inconsistency:
- Read paths treated flow as gone (deleted_at filter)
- Storage still claimed active status with live refs/worktree

## Solution

`soft_delete_flow()` now normalizes deleted records to tombstone state:

1. Set `flow_status='aborted'` (terminal state)
2. Clear all refs (spec_ref, plan_ref, report_ref, audit_ref, indicate_ref, pr_ref)
3. Clear reasons (blocked_reason, failed_reason, blocked_by_issue)
4. Clear worktree_path
5. Clear actor fields (planner_actor, executor_actor, reviewer_actor, manager_actor, latest_actor)
6. Set deleted_at timestamp

## Benefits

- **Audit history**: Row preserved for debugging/recovery
- **Semantic consistency**: Deleted flow no longer claims active refs/worktree
- **Query compatibility**: All active reads filter on deleted_at IS NULL
- **Debugging clarity**: Tombstones clearly marked as aborted

## Implementation

Repository layer: `src/vibe3/clients/sqlite_flow_state_repo.py:soft_delete_flow()`

Tests: `tests/vibe3/test_clients/test_sqlite_flow_state_repo.py`

## Related Issues

- #1070: Full rebuild reset leaves inconsistent soft-deleted rows