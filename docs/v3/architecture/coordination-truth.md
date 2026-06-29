# Orchestra Coordination Truth Architecture

## Overview

This document describes the remote-first coordination truth implementation for orchestra/qualify/coordination reads.

## Truth Table

### Field Priority

**Collaboration Fields (Remote-First):**
- `blocked_reason` - Issue Body Projection > Local SQLite
- `blocked_by_issue` - Issue Body Projection > Local SQLite
- `blocked_by` (multi-value) - Issue Body Projection > Local SQLite

**Execution Fields (Local-Only):**
- `worktree_path` - Local SQLite only
- `actor` - Local SQLite only
- `flow_status` - Derived pointer (reconciled from body truth; see §2.3 of the standard)

### Data Sources

1. **Issue Body Projection** (highest priority for collaboration)
   - Managed section in GitHub issue body
   - Read via `parse_projection_with_fallback()`
   - Source: `DataSource.ISSUE_BODY_FALLBACK`

2. **Local SQLite** (fallback for collaboration, primary for execution)
   - Local flow state database
   - Read via `SQLiteClient.get_flow_state()`
   - Source: `DataSource.LOCAL_SQLITE`

3. **GitHub Issue State** (for dependency checks)
   - Issue open/closed state
   - Read via `GitHubClient.view_issue()`
   - Closed = dependency satisfied

## Degraded Mode

When GitHub API is unavailable:
- Enter degraded mode via `DegradedModeManager`
- Fall back to local SQLite for all reads
- Log degradation event
- Conservative blocking (prefer blocking over dispatching) — see §6.4 of the [standard](../../standards/v3/blocked-dependency-reconciliation-standard.md) for degraded mode protocol

## Integration Points

- `QualifyGateService` - Uses `CoordinationResolver` for blocked/dependency checks
- `GlobalDispatchCoordinator` - Logs degraded mode during dispatch
- `FlowStatusResolver` - Base for remote reads (Issue #945)

## References

- Issue #945: Source-aware flow reads
- Issue #943: Issue body projection
- Issue #942: Remote projection parent issue
- [Blocked/Dependency Reconciliation Standard](../../standards/v3/blocked-dependency-reconciliation-standard.md) — authoritative truth model, unified reconcile primitive (§2/§6), and field ownership table