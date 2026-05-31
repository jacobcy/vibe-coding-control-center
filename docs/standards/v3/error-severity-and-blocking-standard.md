---
document_type: standard
title: Vibe3 Error Severity and Blocking Standard
status: active
scope: orchestra-runtime
authority:
  - failed-gate
  - error-tracking
  - codeagent-execution
author: GPT-5 Codex
created: 2026-05-21
last_updated: 2026-05-21
related_docs:
  - docs/specs/2026-05-21-error-severity-system-refactor-design.md
  - docs/standards/error-handling.md
  - docs/standards/v3/noop-gate-boundary-standard.md
  - docs/standards/vibe3-orchestra-runtime-standard.md
---

# Vibe3 Error Severity and Blocking Standard

## 1. Purpose

This standard defines the canonical runtime semantics for Orchestra error handling.

It exists to prevent the system from mixing these different concepts:

- error severity
- execution contract outcome
- workflow state

This standard is authoritative for:

- `failed_gate`
- runtime error tracking
- codeagent execution classification
- warning visibility in `serve status` and flow timeline

This standard is not the authority for generic Python exception taxonomy.
That remains defined by `docs/standards/error-handling.md`.

## 2. Canonical Terms

### 2.1 Error Severity

Severity classifies how a runtime signal affects overall system availability.

There are exactly three levels:

- `CRITICAL`
- `ERROR`
- `WARNING`

### 2.2 Execution Outcome

Execution outcome classifies whether an agent execution satisfied its role contract.

Canonical outcomes:

- `contract_satisfied`
- `contract_deviated`
- `execution_failed`

### 2.3 Flow State

Flow state classifies the lifecycle status of a task flow.

Examples:

- `running`
- `blocked`
- `done`
- `aborted`
- `stale`

`blocked` is a workflow state, not an error severity.

**Triple-State Synchronization:**
Blocked states are managed across three data sources to ensure consistency and visibility:
1. **Issue Body (Truth):** Authoritative remote state stored in the managed section of the GitHub issue body.
2. **Issue Label (Signal):** Visual indicator of the blocked state.
3. **Database (Cache):** Local performance optimization of the remote state.

These sources are kept in sync by the `BlockedStateService`.

## 3. Severity Definitions

### 3.1 `CRITICAL`

Use `CRITICAL` when the current runtime configuration is unusable.

Properties:

- continued dispatch is unsafe or pointless
- manual intervention is required
- `failed_gate` activates immediately

Examples:

- model not found
- permission denied for configured model
- invalid model/API configuration

### 3.2 `ERROR`

Use `ERROR` when infrastructure is unstable but not yet proven globally unavailable.

Properties:

- may affect one run or several runs
- counts toward failed-gate threshold if configured
- repeated occurrences within the window can activate `failed_gate`

Examples:

- rate limit
- timeout
- service unavailable
- network failure
- confirmed local execution infrastructure failure

### 3.3 `WARNING`

Use `WARNING` for diagnostics, observability signals, and contract-deviation signals
that do not prove runtime unavailability.

Properties:

- must be recorded
- must be visible in status and timeline
- must not activate `failed_gate`
- must not, by themselves, imply `mark_issue(action="fail")`

Examples:

- `codeagent-wrapper` completed without output
- capacity skip
- agent did not satisfy the execution convention and a gate later blocks the flow

## 4. Separation Rules

### 4.1 Severity does not decide workflow state alone

Severity answers:

- "How bad is this for system availability?"

It does not answer:

- "Should the flow become blocked?"
- "Did the role satisfy its contract?"

### 4.2 `blocked` is not a synonym for error

A flow can be blocked for normal orchestration reasons, including:

- missing required ref
- state unchanged after worker completion
- unresolved dependency
- explicit manual hold

These states are often correct and desirable because they expose contract breaks
instead of hiding them behind fake progress.

### 4.3 No-op is a contract result, not a root-cause error

No-op means the agent did not perform the expected state transition or did not
produce the required artifact.

That result may cause the flow to become `blocked`, but no-op itself is not proof
of infrastructure failure.

### 4.4 Unified State Management (BlockedStateService)

All transitions into or out of a `blocked` state must use the `BlockedStateService`. This service coordinates:

- **Atomic Writes:** Updates issue body projection, labels, and local database cache in a single logical operation.
- **Truth Resolution:** Uses the issue body as the authoritative truth, with fallback to the database cache.
- **Synchronization:** The `Qualify Gate` uses this service to align the local cache with the remote truth before starting execution.

## 5. Handling Contract

Each runtime code must resolve through a registry with explicit handling metadata.

Minimum required fields:

- `severity`
- `counts_toward_threshold`
- `record_in_error_log`
- `write_timeline_event`
- `issue_action`
- `gate_action`

Prefix-only policies are forbidden for gate behavior.

Forbidden examples:

- "all `E_EXEC_*` count toward threshold"
- "all caught exceptions automatically fail the issue"

## 6. Failed Gate Rules

`failed_gate` exists to protect the system from continued dispatch during
configuration failure or infrastructure instability.

It may activate only for:

- `CRITICAL`
- thresholded `ERROR`

It must not activate for:

- `WARNING`
- no-op diagnostics
- capacity skip
- contract deviations that are not infrastructure failures

## 7. Warning Rules

Warnings are first-class runtime signals.

Required behavior:

- persist them
- surface them in `serve status`
- emit timeline evidence when relevant
- keep them out of failed-gate threshold counters

Warnings are allowed to coexist with a blocked flow.
In that case:

- the warning explains the diagnostic context
- the workflow block reason explains why the flow stopped

These must remain distinguishable.

## 8. Baseline Code Mapping

### 8.1 Current critical codes

- `E_MODEL_NOT_FOUND`
- `E_MODEL_PERMISSION`
- `E_MODEL_CONFIG`

### 8.2 Current thresholded error codes

- `E_API_RATE_LIMIT`
- `E_API_TIMEOUT`
- `E_API_UNAVAILABLE`
- `E_API_NETWORK`
- `E_API_UNKNOWN`

### 8.3 Current warning codes

- `E_EXEC_NO_OUTPUT`
- `E_CAPACITY_SKIP`

### 8.4 Remaining `E_EXEC_*`

Remaining execution codes are not allowed to inherit gate behavior by prefix.
Each one must be explicitly reviewed and assigned to one of:

- thresholded infrastructure `ERROR`
- diagnostic `WARNING`
- workflow block reason instead of runtime error code

## 9. Display Rules

### 9.1 `serve status`

`serve status` must display at least:

- critical count
- thresholded error count
- warning count
- recent warnings separately from recent critical/error records where possible

### 9.2 Flow timeline

Timeline events must preserve the distinction between:

- warning diagnostics
- workflow blocks
- execution failures

The UI wording must avoid implying that every `blocked` flow is an infrastructure error.

## 10. Review Checklist

When reviewing code against this standard, verify:

- `failed_gate` only reacts to `CRITICAL` and thresholded `ERROR`
- warning-only records never contribute to failed-gate thresholding
- `blocked` is rendered and logged as a workflow state
- no-op and no-output are not presented as root-cause infrastructure failures
- every runtime code is resolved by explicit registry metadata rather than prefix inference

## 11. ERROR/BLOCK Orthogonality (Phase 1-3 Refactor)

### 11.1 Architectural Separation

After the Phase 1-3 refactor (2026-05-23), ERROR and BLOCK systems are **completely orthogonal**:

| System | Purpose | Data Store | Triggers |
|--------|---------|------------|----------|
| **ERROR** | Runtime infrastructure health | `error_log` table | FailedGate dispatch control |
| **BLOCK** | Business flow state | `blocked_reason` field | Business logic decisions |

### 11.2 Exception Type Hierarchy

```
VibeError (base)
├── RuntimeInfrastructureError  → error_log only, NO block_flow
│   ├── GitHubAPIError
│   ├── DatabaseError
│   ├── ModelError
│   └── APIError
└── BusinessViolation  → may trigger block_flow
    ├── NoOpViolation
    ├── DependencyViolation
    ├── TransitionLoopViolation
    └── RequiredRefViolation
```

### 11.3 Key Invariants

1. **`fail_*_issue()`** → `mark_issue(action="fail")` → records to `error_log` only
2. **`block_*_issue()`** → `mark_issue(action="block")` → calls `block_flow()`
3. **`GitHubAPIError`** → propagates to `codeagent_runner` → records to `error_log`, NO block
4. **`FailedGate`** → blocks **dispatch coordination**, NOT business flow

### 11.4 StateVerificationService

GitHub API state verification is isolated in `StateVerificationService`:
- Handles retry logic with limits
- Raises `GitHubAPIError` on failure (runtime error)
- Never triggers `block_flow()`
- External I/O is separated from business logic in `noop_gate`

### 11.5 Audit Results (Phase 3)

All `block_flow()` call sites audited:
- 9 call sites verified
- No error strings passed as `reason` parameter
- All `reason` values are business logic descriptions

All `error_log` consumers audited:
- FailedGate: dispatch-level blocking only
- Status services: display only
- No consumer triggers `block_flow()`

## 12. Authority

If existing code conflicts with this document, this standard governs the Orchestra
runtime refactor introduced on 2026-05-21 and the ERROR/BLOCK decoupling refactor
completed on 2026-05-23.
