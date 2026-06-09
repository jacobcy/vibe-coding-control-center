# Blocked State Architecture Design

**Author**: System Analysis  
**Date**: 2026-05-23  
**Status**: Implemented  
**Related Issues**: #904, #1008, #1314 (closed)

---

## Executive Summary

The current implementation has a **triple-state desynchronization problem** where database, issue body, and issue label can hold inconsistent blocked state information. This document proposes a unified architecture that establishes clear ownership and synchronization patterns.

---

## Problem Statement

### Current State

Three independent sources track blocked state:

1. **Database** (`flow_state` table)
   - `flow_status`: "active" | "blocked" | "done" | "aborted"
   - `blocked_reason`: TEXT
   - `blocked_by_issue`: INT

2. **Issue Body** (HTML comment section)
   - `state`: "active" | "blocked" | "done" | "aborted"
   - `blocked_reason`: TEXT
   - `blocked_by`: comma-separated INT list

3. **Issue Labels** (GitHub labels)
   - `state/blocked`: presence indicates blocked

### Issues

1. **Inconsistent writes**: Different code paths update different subsets
   - `BlockedStateService.block(issue_number=...)` → writes all three ✅
   - `BlockedStateService.block()` (no issue_number) → writes DB only ✅
   - `fail_flow()` → (Retired) legacy mechanism ❌
   - `task resume --label` → writes all three ✅
   - `qualify_gate` alignment → writes all three ✅

2. **No single source of truth**: Conflicts arise when states disagree

3. **Cross-machine synchronization**: Database is local-only; remote workers can't see it

4. **Timing issues**: Partial writes can leave inconsistent state

---

## Design Principles

### 1. Remote-First Truth Source

**Issue body + labels = Authoritative Truth**

- **Why**: 
  - Shared across all worktrees and machines
  - Survives database deletion
  - Human-visible and debuggable
  - Works in degraded mode (GitHub API failure)

- **Implication**: Local database is a **cache** for performance, not a truth source

### 2. Cache Coherence Protocol

**Qualify Gate = Cache Synchronizer**

- **When**: Before every dispatch attempt
- **What**: 
  1. Read authoritative truth from issue body
  2. Update local cache (database) to match
  3. Proceed with dispatch decision

- **Why**: Ensures cache is always coherent with truth before critical operations

### 3. Single Write Path

**All state changes go through BlockedStateService**

- **Before**: Multiple services write directly to DB/body/labels
- **After**: Centralized service ensures atomic, consistent updates

---

## Architecture

### Component Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                   BlockedStateService                    │
│  (Single entry point for all blocked state operations)  │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         ▼           ▼           ▼
    ┌────────┐  ┌─────────┐  ┌────────┐
    │Database│  │Body API │  │ Label  │
    │ (cache)│  │(truth)  │  │(signal)│
    └────────┘  └─────────┘  └────────┘
```

### Truth Hierarchy

```
Issue Body (Remote Truth)
    ↓ (on conflict)
Database (Local Cache)
    ↓ (when remote unavailable)
None (degraded mode)
```

### Data Flow

**Block Flow**:
```
User/Agent Request
    ↓
BlockedStateService.block()
    ↓
├─ Write Issue Body (truth)
├─ Write Database (cache)
└─ Write Label (signal)
```

**Resume Flow**:
```
User Request (task resume --label)
    ↓
BlockedStateService.unblock()
    ↓
├─ Read Issue Body (verify truth)
├─ Clear Issue Body
├─ Clear Database
└─ Clear Label
```

**Dispatch Flow**:
```
Dispatch Intent
    ↓
Qualify Gate
    ↓
├─ Read Issue Body (truth)
├─ Sync Database (cache)
├─ Check dependencies
└─ Proceed/Block
```

---

## Implementation Plan

### Phase 1: Core Service (High Priority)

Create `src/vibe3/services/blocked_state_service.py`:

```python
class BlockedStateService:
    """Unified blocked state management service.
    
    Truth Model:
    - Issue body + labels = Authoritative (remote-first)
    - Database = Cache (performance optimization)
    - Qualify gate = Synchronizer (ensures coherence)
    """
    
    def block(
        self,
        branch: str,
        reason: str,
        blocked_by_issue: int | None = None,
        actor: str = "system",
    ) -> None:
        """Atomically set blocked state in all three sources.
        
        Order: Body (truth) → DB (cache) → Label (signal)
        """
        ...
    
    def unblock(
        self,
        branch: str,
        target_state: IssueState,
        actor: str = "human:resume",
    ) -> None:
        """Atomically clear blocked state in all three sources.
        
        Order: Body (truth) → DB (cache) → Label (signal)
        """
        ...
    
    def sync_cache_from_truth(
        self,
        branch: str,
        issue_number: int,
    ) -> BlockedState:
        """Synchronize local cache (DB) from authoritative truth (body).
        
        Called by qualify gate before dispatch.
        Returns current blocked state after sync.
        """
        ...
    
    def resolve_truth(
        self,
        branch: str,
        issue_number: int,
    ) -> BlockedState:
        """Read authoritative truth from issue body.
        
        Fallback to database cache if body read fails.
        """
        ...

---

## Implementation Plan

### Phase 1: Core Service (High Priority) ✅ Completed

Create `src/vibe3/services/blocked_state_service.py`:

...

### Phase 2: Retire Legacy Mechanisms (High Priority) ✅ Completed

1. **Retire `fail_flow()`**: Remove legacy calls and migrate to `BlockedStateService.block()`
2. **Remove PR 1314 changes**: Revert incorrect `handoff_service.py` modification
3. **Add validation**: Ensure `block()` always writes all three sources

### Phase 3: Refactor Consumers (Medium Priority) ✅ Completed

1. **flow_block_mixin.py**: Use BlockedStateService
2. **task_resume_operations.py**: Use BlockedStateService
3. **qualify_gate.py**: Use `sync_cache_from_truth()`
4. **issue_failure_service.py**: Use BlockedStateService

### Phase 4: Testing (High Priority) 🔄 In Progress

1. **Unit tests**: BlockedStateService methods
2. **Integration tests**: Three-source consistency
3. **Race condition tests**: Concurrent writes
4. **Degraded mode tests**: GitHub API failure scenarios


---

## API Design

### BlockedStateService Public API

```python
# Block operations
def block(branch, reason, blocked_by_issue=None, actor="system") -> None
def unblock(branch, target_state, actor="human:resume") -> None

# Query operations
def is_blocked(branch, issue_number) -> bool
def get_blocked_reason(branch, issue_number) -> str | None
def get_blocked_by(branch, issue_number) -> list[int]

# Synchronization
def sync_cache_from_truth(branch, issue_number) -> BlockedState
def resolve_truth(branch, issue_number) -> BlockedState

# Validation
def validate_consistency(branch, issue_number) -> ConsistencyReport
```

### ConsistencyReport Model

```python
@dataclass
class ConsistencyReport:
    """Report on three-source consistency."""
    database_state: BlockedState
    body_state: BlockedState
    label_state: BlockedState
    
    @property
    def is_consistent(self) -> bool:
        """True if all three sources agree."""
        ...
    
    @property
    def authoritative_state(self) -> BlockedState:
        """Returns the truth-source state."""
        return self.body_state
```

---

## Migration Path

### Backward Compatibility

1. **Phase 1**: Add BlockedStateService (no breaking changes)
2. **Phase 2**: Migrate internal callers one-by-one
3. **Phase 3**: Deprecate direct writes to DB/body/labels
4. **Phase 4**: Remove legacy code paths

### Rollout Strategy

1. **Feature flag**: `use_blocked_state_service` (default: False)
2. **Gradual migration**: Migrate one service at a time
3. **Monitoring**: Alert on consistency violations
4. **Rollback**: Can disable flag if issues arise

---

## Edge Cases

### GitHub API Failure (Degraded Mode)

**Scenario**: Cannot read/write issue body

**Behavior**:
1. Use database cache as fallback
2. Log degraded mode warning
3. Continue operation (availability > consistency)

**Recovery**: On next successful API call, sync cache → truth

### Concurrent Writes

**Scenario**: Two processes try to block same issue simultaneously

**Solution**:
1. Issue body is write-once per event (use timeline events as sequence)
2. Database uses transaction isolation
3. Labels use GitHub optimistic concurrency

### Partial Failures

**Scenario**: Body write succeeds, DB write fails

**Solution**:
1. Log error but don't fail operation
2. Next `sync_cache_from_truth()` will repair DB
3. Truth source (body) is authoritative

---

## Success Metrics

1. **Consistency**: All three sources agree 100% of time after any operation
2. **Performance**: < 100ms overhead for sync operations
3. **Reliability**: Graceful degradation on API failures
4. **Debuggability**: Clear audit trail in timeline events

---

## Open Questions

1. **Q**: Should we merge `blocked_by_issue` (DB single INT) and `blocked_by` (body list)?
   **A**: Keep separate for now. DB tracks primary blocker, body tracks all blockers.

2. **Q**: How to handle `dependencies` vs `blocked_by` semantic overlap?
   **A**: Document that `dependencies` = managed deps, `blocked_by` = blocking deps.

3. **Q**: Should `BlockedStateService.block()` set `flow_status="blocked"` in DB?
   **A**: Yes, for consistency. This ensures the local cache matches the authoritative truth.

---

## References

- [Qualify Gate Design](../standards/v3/qualify-gate.md)
- [Issue Body Projection Format](../standards/v3/issue-body-projection.md)
