# ERROR/BLOCK Separation Architecture

## Design Principle

ERROR tracking and BLOCK management are two orthogonal systems that serve different purposes and must remain decoupled.

| | ERROR System | BLOCK System |
|---|---|---|
| **Purpose** | Track error frequency for threshold detection | Manage issue flow state (block/unblock) |
| **Storage** | `error_log` table in SQLite | `blocked_state` table in SQLite |
| **Trigger** | Exceptions, API failures, recovery events | Manual block, auto-block via FailedGate |
| **Output** | Error count, threshold reached flag | Blocked/unblocked state, fail issue |

## ERROR System

### Storage

Errors are stored in the `error_log` SQLite table via `ErrorTrackingService`.

### Control Flow

1. Exception occurs in execution layer
2. Error is classified via `classify_error_hybrid()`
3. Error is recorded via `record_error()` convenience function
4. `ErrorTrackingService` writes to `error_log` table
5. `FailedGate.check()` reads `error_log` on heartbeat tick
6. If threshold reached, `FailedGate` triggers BLOCK

### Recording Errors

Use the `record_error()` convenience function from `error_helpers`:

```python
from vibe3.exceptions.error_helpers import record_error

# Minimal call
record_error(
    error_code="E_MODEL_NOT_FOUND",
    error_message="Model xyz not found",
)

# With all parameters
record_error(
    error_code="E_API_RATE_LIMIT",
    error_message="GitHub API rate limit exceeded",
    tick_id=42,
    issue_number=1357,
    branch="task/issue-1357",
    store=store_instance,
    severity=ErrorSeverity.HIGH,
)
```

### Error Codes

Pre-registered error codes live in `vibe3.exceptions.error_codes`:

- `E_MODEL_*` — Model/preset resolution errors
- `E_API_*` — External API errors (rate limit, unavailable)
- `E_EXEC_*` — Execution engine errors

### Error Severity

Severity levels are defined in `vibe3.exceptions.error_severity` and mapped via error handling contracts in `vibe3.exceptions.error_classification`.

## BLOCK System

### Storage

Blocked states are stored in the `blocked_state` SQLite table via `BlockedStateService`.

### Control Flow

1. Block condition triggered (manual or auto via FailedGate)
2. `block_flow()` is called via `FlowBlockMixin`
3. `BlockedStateService` writes to `blocked_state` table
4. Issue label set to `state/blocked`
5. Unblock removes the state and restores issue label

### Blocking Flows

Use the `block_flow()` function from `flow_block_mixin`:

```python
from vibe3.services.flow_block_mixin import block_flow

block_flow(
    store=store_instance,
    branch="task/issue-1357",
    issue_number=1357,
    reason="Auto-blocked: error threshold exceeded",
)
```

## When to Use Which System

| Scenario | System | Function |
|----------|--------|----------|
| API call fails | ERROR | `record_error()` |
| Error count exceeds threshold | BLOCK (via FailedGate) | Automatic |
| Manual issue blocking | BLOCK | `block_flow()` |
| Scene recovery triggered | ERROR | `record_error()` |
| Governance scan fails | ERROR | `record_error()` |
| Issue needs human attention | BLOCK | `block_flow()` |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Execution Layer                       │
│  (codeagent_runner, dispatch, auto_scene_recovery, ...) │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
        record_error()          block_flow()
               │                      │
               ▼                      ▼
┌──────────────────────┐  ┌──────────────────────┐
│   ERROR System       │  │   BLOCK System       │
│                      │  │                      │
│ ErrorTrackingService │  │ BlockedStateService  │
│ error_log table      │  │ blocked_state table  │
│ error_classification │  │ flow_block_mixin     │
│ error_codes          │  │ blocked_state_io     │
│ error_helpers        │  │ blocked_state_types  │
└──────────┬───────────┘  └──────────────────────┘
           │                       ▲
           │  threshold reached    │
           └───────────────────────┘
              FailedGate (read-only)
```

Key constraint: ERROR system writes to `error_log`, BLOCK system writes to `blocked_state`. The only coupling point is `FailedGate`, which reads `error_log` (read-only) and may trigger a BLOCK.
