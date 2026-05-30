# Flow Timeline Comments Standard

> **Status**: Implemented (Issue #944)
> **Last Updated**: 2026-05-17

## Overview

This document defines the unified `[flow]` marker standard for all flow state change comments on GitHub issues, including deduplication strategy and implementation guidelines.

## Purpose

**Problem**: Prior to this standard, flow state changes used inconsistent comment markers:
- `flow_block_mixin.py` used manual `GitHubClient.add_comment()` with inconsistent markers
- `issue_failure_service.py` used role-based markers (`[manager]`, `[plan]`, `[run]`, `[review]`)
- `task_resume_operations.py` used `[resume]` marker for rollback comments

**Solution**: Unified `[flow]` marker with centralized `FlowTimelineService` providing:
1. **Consistent formatting**: All flow state changes use `[flow]` marker
2. **Stable dedupe semantics**: Skip duplicate comments with same event_type
3. **Single source of truth**: One service handles both event recording and comment posting

## [flow] Marker Standard

### Definition

The `[flow]` marker is added to `AUTOMATED_MARKERS` tuple in `src/vibe3/utils/constants.py`:

```python
AUTOMATED_MARKERS: Final[tuple[str, ...]] = (
    "[manager]",
    "[flow]",  # Unified flow timeline marker
    "[resume]",
    "[plan]",
    "[run]",
    "[review]",
    "[apply]",
    "[orchestra]",
    "[handoff]",
    "[governance suggest]",
    "[governance auto-recover]",
    "[governance apply]",
    "[governance]",
)
```

### Usage

**All flow state changes must use `[flow]` marker**:

| Event Type | Display Text | Comment Format | 备注 |
|------------|--------------|----------------|------|
| `flow_blocked` | "Flow blocked" | `[flow] Flow blocked\n\n{detail}` | 业务阻塞 (BLOCK 系统) |
| `flow_failed` | "Flow failed" | `[flow] Flow failed\n\n{detail}` | 运行时错误 (ERROR 系统)，调用者按惯例省略 `issue_number` |
| `flow_aborted` | "Flow aborted" | `[flow] Flow aborted\n\n{detail}` | 流程中止 |
| `resumed` | "Flow resumed" | `[flow] Flow resumed\n\n{detail}` | 流程恢复 |
| `state_transitioned` | "State transitioned" | `[flow] State transitioned\n\n{detail}` | 状态迁移 |

**Note**: According to the [Error Severity Standard](../standards/v3/error-severity-and-blocking-standard.md), runtime infrastructure failures (`flow_failed`) are recorded in the SQLite `error_log` and `events` table. Callers such as `IssueFailureService.mark_issue(action="fail")` **omit the `issue_number` parameter** to avoid posting noise comments. Only business-level blocks that require human intervention pass `issue_number` and post `[flow]` comments.

**Example**:

```python
# Old: role-based markers
"[manager] 管理执行报错,已切换为 state/blocked。\n\n原因:{reason}"
"[plan] 规划执行完成，但未登记 authoritative，已切换为 state/blocked。\n\n原因:{reason}"

# New: unified [flow] marker
"[flow] Flow blocked\n\n已切换为 state/blocked。\n\n原因:{reason}"
"[flow] Flow failed\n\n原因:{reason}"
```

## FlowTimelineService

### Architecture

```
FlowTimelineService
  ├─ record_timeline_event() — Main entry point
  ├─ _build_timeline_comment() — Build [flow] comment body
  └─ _should_skip_duplicate_comment() — Dedupe logic
```

### Core Methods

#### `record_timeline_event()`

**Signature**:

```python
def record_timeline_event(
    self,
    branch: str,
    event_type: str,
    actor: str,
    detail: str,
    issue_number: int | None = None,
) -> None
```

**Behavior**:
1. Always record event in SQLite (`store.add_event()`)
2. Skip GitHub comment if `issue_number is None`
3. Apply dedupe logic: check latest comment for same event_type
4. Add `[flow]` comment to GitHub issue if not skipped

**Example**:

```python
timeline_service = FlowTimelineService(store=store)
timeline_service.record_timeline_event(
    branch="task/issue-42",
    event_type="flow_blocked",
    actor="agent:manager",
    detail="Blocked by dependency #456",
    issue_number=42,
)
```

### Dedupe Strategy

**Goal**: Prevent duplicate `[flow]` comments for repeated state transitions with same event_type.

**Implementation**:

```python
def _should_skip_duplicate_comment(
    self, issue_number: int, event_type: str
) -> bool:
    """Check if latest timeline comment has same event_type."""
    # 1. Fetch latest comment from issue
    latest_comment = self._get_latest_comment(issue_number)

    # 2. Check if comment has [flow] marker
    if not latest_comment.startswith("[flow]"):
        return False

    # 3. Extract display text from comment
    # Pattern: "[flow] {display_text}"
    display_text = self._extract_display_text(latest_comment)

    # 4. Map display text back to event_type
    reverse_map = {
        "Flow blocked": "flow_blocked",
        "Flow failed": "flow_failed",
        "Flow aborted": "flow_aborted",
        "Flow resumed": "resumed",
        "State transitioned": "state_transitioned",
    }
    latest_event_type = reverse_map.get(display_text)

    # 5. Skip if same event_type
    return latest_event_type == event_type
```

**Example**:

```python
# Scenario: Manager blocks flow twice with different reasons

# First block
timeline_service.record_timeline_event(
    branch="task/issue-42",
    event_type="flow_blocked",
    detail="Blocked by #456",
)
# Result: [flow] comment added

# Second block (same event_type, different detail)
timeline_service.record_timeline_event(
    branch="task/issue-42",
    event_type="flow_blocked",
    detail="Blocked by #789",
)
# Result: SQLite event recorded, but comment SKIPPED (dedupe)
```

## Integration Points

### 1. flow_block_mixin.py

**Before**:

```python
# Manual comment with inconsistent marker
github_client = GitHubClient()
github_client.add_comment(
    issue_number,
    f"[manager] Flow blocked: {reason}",
)
```

**After**:

```python
# Unified [flow] marker via FlowTimelineService
timeline_service = FlowTimelineService(store=self.store)
timeline_service.record_timeline_event(
    branch=branch,
    event_type="flow_blocked",
    actor=effective_actor,
    detail=reason,
    issue_number=issue_number,
)
```

### 2. issue_failure_service.py

**After**:

```python
# Unified [flow] marker via FlowTimelineService
timeline_service = FlowTimelineService(store=store)

if action == "fail":
    # Runtime failures do NOT post GitHub comments
    timeline_service.record_timeline_event(
        branch=branch,
        event_type="flow_failed",
        actor=actor,
        detail=reason,
        # issue_number omitted
    )
else:
    # Business blocks DO post GitHub comments
    timeline_service.record_timeline_event(
        branch=branch,
        event_type="flow_blocked",
        actor=actor,
        detail=reason,
        issue_number=issue_number,
    )
```

### 3. task_resume_operations.py

**Before**:

```python
# Manual rollback comment with [resume] marker
github_client.add_comment(
    issue_number,
    "[resume] task scene 重置失败，已恢复为 state/{state}。\n\n原因:{reason}",
)
```

**After**:

```python
# Unified [flow] marker via FlowTimelineService
timeline_service = FlowTimelineService(store=self.flow_service.store)
timeline_service.record_timeline_event(
    branch=branch,
    event_type="resumed",
    actor="human:resume",
    detail=f"Rollback to state/{state} due to scene reset failure: {reason}",
    issue_number=issue_number,
)
```

## Event Type Mapping

### Display Text Mapping

```python
display_map = {
    "flow_blocked": "Flow blocked",
    "flow_failed": "Flow failed",
    "flow_aborted": "Flow aborted",
    "resumed": "Flow resumed",
    "state_transitioned": "State transitioned",
}
```

**Usage**:

1. **Forward mapping**: Build comment header from event_type
   ```python
   display_text = display_map.get(event_type, event_type.replace("_", " ").title())
   comment = f"[flow] {display_text}\n\n{detail}"
   ```

2. **Reverse mapping**: Extract event_type from comment header
   ```python
   reverse_map = {v: k for k, v in display_map.items()}
   event_type = reverse_map.get(display_text)
   ```

## Testing

### Test Coverage

**FlowTimelineService Tests** (`tests/vibe3/services/test_flow_timeline_service.py`):
- `test_record_timeline_event_creates_event_and_comment` — Basic functionality
- `test_record_timeline_event_skips_comment_if_no_issue` — No issue_number case
- `test_record_timeline_event_dedupe_skips_same_event_type` — Dedupe logic
- `test_record_timeline_event_allows_different_event_type` — Different event_type allowed

**Integration Tests**:
- `test_flow_block_enhanced.py` — block_flow() integration
- `test_issue_failure_service.py` — fail/block_issue integration
- `test_task_resume_operations.py` — rollback comment integration

### Running Tests

```bash
# FlowTimelineService tests
uv run pytest tests/vibe3/services/test_flow_timeline_service.py -v

# Integration tests
uv run pytest tests/vibe3/services/test_flow_block_enhanced.py -v
uv run pytest tests/vibe3/services/test_issue_failure_service.py -v
uv run pytest tests/vibe3/services/test_task_resume_operations.py -v

# All flow-related tests
uv run pytest tests/vibe3/services/ -k "flow|timeline|resume" -v
```

## Best Practices

### 1. Always Use FlowTimelineService

**Rule**: Never use `GitHubClient.add_comment()` directly for flow state changes.

**Reason**:
- Ensures consistent `[flow]` marker
- Automatic dedupe logic
- Single source of truth

### 2. Provide issue_number When Available

**Rule**: Always pass `issue_number` to `record_timeline_event()` when flow has linked issue.

**Reason**:
- Enables GitHub comment posting
- Enables dedupe logic
- Provides timeline visibility

### 3. Handle Exceptions Gracefully

**Pattern**:

```python
try:
    timeline_service = FlowTimelineService(store=store)
    timeline_service.record_timeline_event(
        branch=branch,
        event_type="flow_blocked",
        actor=actor,
        detail=reason,
        issue_number=issue_number,
    )
except Exception as e:
    logger.bind(
        domain="flow",
        action="timeline",
        issue_number=issue_number,
        error=str(e),
    ).warning("Timeline comment failed")
    # Continue execution - timeline comment failure is non-blocking
```

**Reason**: Timeline comments are side effects, not critical operations.

### 4. Use Correct event_type

**Mapping**:

| Operation | event_type |
|-----------|------------|
| `BlockedStateService.block()` | `"flow_blocked"` |
| `abort_flow()` | `"flow_aborted"` |
| `resume_issue()` | `"resumed"` |
| State transition | `"state_transitioned"` |

**Wrong**:

```python
# ❌ Wrong: Using raw event_type without prefix
timeline_service.record_timeline_event(
    event_type="blocked",  # Should be "flow_blocked"
)
```

**Correct**:

```python
# ✅ Correct: Using standardized event_type
timeline_service.record_timeline_event(
    event_type="flow_blocked",
)
```

## Future Enhancements

### Potential Extensions

1. **Extended event types**:
   - `flow_created` — Flow creation event
   - `flow_reactivated` — Flow reactivation event
   - `flow_merged` — PR merge event

2. **Comment threading**:
   - Reply to previous `[flow]` comment for context continuity
   - Use GitHub comment threads for related events

3. **Timeline visualization**:
   - Generate timeline summary from SQLite events
   - Provide `vibe3 flow timeline` command

## References

- **Issue #944** — Original specification
- **src/vibe3/services/flow_timeline_service.py** — Implementation
- **src/vibe3/utils/constants.py** — AUTOMATED_MARKERS definition
- **docs/standards/glossary.md** — Term definitions