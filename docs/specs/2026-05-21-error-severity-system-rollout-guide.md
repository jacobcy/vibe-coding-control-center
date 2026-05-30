# Error Severity Refactor Rollout Guide

**Date**: 2026-05-21
**Scope**: `src/vibe3` current runtime implementation
**Status**: Draft

## Purpose

This document turns the refactor spec into an executable guide for the current codebase.

Use it during implementation and again during verification to answer:

1. what must change
2. in which files
3. what behavior must be preserved
4. how to tell whether the refactor actually met the standard

## Source of Truth

Implementation must conform to:

- `docs/specs/2026-05-21-error-severity-system-refactor-design.md`
- `docs/standards/v3/error-severity-and-blocking-standard.md`

If this guide and the standard disagree, the standard wins.

## Current Code Inventory

### Classification and codes

- `src/vibe3/exceptions/error_codes.py`
- `src/vibe3/exceptions/error_classification.py`

### Tracking and gate behavior

- `src/vibe3/exceptions/error_tracking.py`
- `src/vibe3/orchestra/failed_gate.py`

### Execution path

- `src/vibe3/execution/codeagent_runner.py`
- `src/vibe3/execution/governance_sync_runner.py`

### Status and presentation

- `src/vibe3/services/serve_status_service.py`
- `src/vibe3/commands/status_render.py`

### Workflow semantics and gate boundaries

- `docs/standards/vibe3-noop-gate-boundary-standard.md`
- related no-op gate and issue failure service call sites

## Current Behavior to Replace

### 1. Prefix-based gate policy

Current behavior:

- `error_tracking` counts both API and EXEC errors toward threshold
- `failed_gate` checks `API + EXEC` threshold by prefix

Target behavior:

- only threshold-eligible `ERROR` records count
- warning-only execution signals never activate `failed_gate`

### 2. Exception means issue failure

Current behavior:

- execution exceptions are recorded
- flow timeline is written as aborted/blocked
- issue is failed except for explicit capacity skip

Target behavior:

- severity/disposition controls the action
- warning diagnostics do not automatically fail the issue
- flow blocking comes from workflow/gate semantics, not from every caught exception

### 3. Status surfaces collapse warnings into errors

Current behavior:

- `serve status` reports total/model/api/execution errors
- warning-only signals are not given their own semantic space

Target behavior:

- warnings are visible as warnings
- critical/error counts remain distinct from warning counts

## File-by-File Work Plan

### Step 1: Introduce severity metadata

Files:

- `src/vibe3/exceptions/error_codes.py`
- `src/vibe3/exceptions/error_classification.py`

Required changes:

- add `ErrorSeverity`
- add registry-backed metadata structure
- add a classification path that returns code plus handling metadata
- preserve backward-compatible code constants

Acceptance checks:

- classification can resolve `severity`
- no caller needs to infer gate behavior from string prefix alone

### Step 2: Refactor error tracking

Files:

- `src/vibe3/exceptions/error_tracking.py`
- any SQLite schema/query helpers used by it

Required changes:

- store severity-aware records
- split threshold counters from diagnostic counters
- add warning-aware query methods

Acceptance checks:

- `E_EXEC_NO_OUTPUT` is persisted but not counted toward threshold
- warning counts can be queried independently

### Step 3: Refactor failed gate

Files:

- `src/vibe3/orchestra/failed_gate.py`

Required changes:

- stop querying `get_api_and_exec_error_count()`
- query only threshold-eligible error counts
- keep immediate activation for critical configuration failures

Acceptance checks:

- two `E_EXEC_NO_OUTPUT` records do not close the gate
- repeated API failures still close the gate
- model configuration failures still close the gate immediately

### Step 4: Refactor execution handlers

Files:

- `src/vibe3/execution/codeagent_runner.py`
- `src/vibe3/execution/governance_sync_runner.py`

Required changes:

- replace exception-to-issue-failure default path with severity/disposition handling
- emit warning timeline events for warning-classified signals
- prevent warning-only signals from auto-blocking the flow

Acceptance checks:

- `E_CAPACITY_SKIP` remains non-blocking
- `E_EXEC_NO_OUTPUT` becomes warning-only
- confirmed infrastructure failures still produce blocking/failure behavior when appropriate

### Step 5: Align no-op/block semantics

Files:

- no-op gate call sites
- issue failure/blocking service call sites touched by execution refactor

Required changes:

- make block reasons explicit
- separate "contract deviation" from "runtime infrastructure failure"
- keep `blocked` as normal workflow state

Acceptance checks:

- missing ref / unchanged state are represented as workflow block reasons
- logs and timeline text do not imply they are system availability failures

### Step 6: Update status and display

Files:

- `src/vibe3/services/serve_status_service.py`
- `src/vibe3/commands/status_render.py`

Required changes:

- add warning counts and recent warning display
- adjust wording so blocked flow != system error
- keep recent critical/error diagnostics readable

Acceptance checks:

- operator can tell at a glance whether the system is unavailable or only emitting warnings

## Tests to Update or Add

### Existing test areas likely affected

- `tests/test_error_classification.py`
- `tests/vibe3/exceptions/test_error_tracking.py`
- `tests/vibe3/test_dispatch_error_propagation.py`
- `tests/vibe3/orchestra/test_failed_gate.py`
- tests covering `serve status` rendering

### Required new assertions

1. `E_EXEC_NO_OUTPUT` resolves to `WARNING`
2. warning-only records do not increment failed-gate threshold counters
3. two warning-only events do not activate `failed_gate`
4. repeated API `ERROR` events still activate `failed_gate`
5. model `CRITICAL` events still activate `failed_gate` immediately
6. warning diagnostics are visible in status output
7. block reasons from no-op behavior are distinguishable from infrastructure failures

## Verification Matrix

### Scenario A: model misconfiguration

Setup:

- raise `ProviderModelNotFoundError` or equivalent mapping

Expected:

- classified as `CRITICAL`
- recorded as critical
- `failed_gate` activates immediately

### Scenario B: transient API instability

Setup:

- one timeout or one rate limit

Expected:

- classified as `ERROR`
- recorded as threshold-eligible error
- gate remains open after one event

### Scenario C: repeated API instability

Setup:

- reach configured threshold within time window

Expected:

- `failed_gate` activates
- reason text references infrastructure threshold, not execution prefix

### Scenario D: wrapper no output but work later proves valid

Setup:

- produce `E_EXEC_NO_OUTPUT`
- noop gate evidence later shows state/ref success

Expected:

- warning recorded
- timeline warning visible
- no failed-gate activation
- no automatic issue failure from warning alone

### Scenario E: worker contract deviation

Setup:

- role exits without required ref or without required state change

Expected:

- flow becomes `blocked` through workflow/gate semantics
- diagnostic record may exist as warning
- system does not represent this as global infrastructure failure

## Completion Checklist

- [ ] registry-backed severity model exists
- [ ] failed-gate thresholding ignores warning-only records
- [ ] `E_EXEC_NO_OUTPUT` is warning-only
- [ ] `serve status` separates warnings from critical/error conditions
- [ ] timeline distinguishes warning diagnostics from blocked workflow state
- [ ] no-op outcomes are represented as contract/block semantics, not infrastructure errors
- [ ] tests cover all severity classes and blocked semantics

## Exit Criteria

The refactor is complete only when all of the following are true:

1. implementation matches `error-severity-and-blocking-standard`
2. all affected tests pass
3. warning-only scenarios no longer trigger failed-gate closure
4. blocked workflow scenarios are rendered as workflow outcomes rather than system failures
