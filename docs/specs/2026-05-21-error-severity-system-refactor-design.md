# Error Severity and Blocking Semantics Refactor

**Date**: 2026-05-21
**Author**: Claude + Yi Chen
**Status**: Draft

## Summary

This refactor establishes a unified runtime semantics model for Orchestra error handling.

The core change is not just "reclassify error codes." The system must separate three
orthogonal concepts that are currently mixed together:

1. **Error Severity**: `CRITICAL / ERROR / WARNING`
2. **Execution Outcome**: whether the agent satisfied its execution contract
3. **Flow State**: `running / blocked / done / aborted / stale`

The design goal is:

- `CRITICAL`: current configuration is unusable, stop the system immediately
- `ERROR`: infrastructure is unstable, track by threshold, then stop the system
- `WARNING`: record and surface diagnostics, but do not stop the system
- `BLOCKED`: a normal workflow state, not an error severity

## Problem

### Current semantic confusion

The current implementation mixes at least three different questions into one path:

1. **What went wrong technically?**
2. **Did the agent satisfy its contract?**
3. **Should the flow be blocked?**

This leads to incorrect behavior:

- `E_EXEC_NO_OUTPUT` is treated as an error that blocks work
- `E_EXEC_*` contributes to `failed_gate` thresholding
- `blocked` is often treated as an error result rather than a normal workflow state
- observability signals and infrastructure failures share the same handling path

### Concrete examples

Issue patterns such as `#1088` and `#1108` showed:

- plan/report refs existed
- issue state changed
- git work was produced
- the run was still blocked because `codeagent-wrapper` emitted no output

That is a contract-observability problem, not an infrastructure failure.

## Goals

1. Define a single runtime standard for Orchestra error severity and blocking semantics.
2. Make `failed_gate` care only about real system unavailability.
3. Make `warning` signals visible in `flow timeline` and `serve status`.
4. Make `blocked` explicitly represent a workflow state rather than an error class.
5. Preserve existing error code constants where possible while changing handling behavior.

## Non-Goals

1. Rewriting all exception types used by CLI and non-Orchestra code.
2. Replacing the existing `SystemError / UserError / BatchError` standard for generic Python code.
3. Changing business ownership boundaries defined by the no-op gate and manager workflow.
4. Completing every follow-on implementation in this document.

## Relationship to Existing Standards

This refactor introduces a runtime standard for Orchestra dispatch and execution.
It does **not** replace the general-purpose exception taxonomy in
`docs/standards/error-handling.md`.

The distinction is:

- `docs/standards/error-handling.md` answers:
  "How should Python code and CLI commands model exceptions?"
- this refactor answers:
  "How should Orchestra runtime signals affect failed gate, flow blocking, and observability?"

Both standards must remain compatible, but they serve different layers.

## Canonical Model

### 1. Error Severity

Severity answers:
**Does this signal indicate system unavailability, unstable infrastructure, or only a diagnostic warning?**

#### `CRITICAL`

Meaning:

- current runtime configuration is unusable
- continued dispatch is unsafe or pointless

Examples:

- model not found
- model permission denied
- invalid model/API configuration

Effect:

- record as critical
- `failed_gate` activates immediately
- new dispatch is blocked until manual recovery

#### `ERROR`

Meaning:

- current infrastructure is unstable or failing
- a single occurrence does not always justify global shutdown
- repeated occurrences within a time window justify stopping dispatch

Examples:

- API rate limit
- API timeout
- service unavailable
- network failures
- confirmed local execution infrastructure failures

Effect:

- record as error
- count toward threshold
- `failed_gate` activates only when threshold is reached

#### `WARNING`

Meaning:

- diagnostic or contract-deviation signal
- useful for visibility and debugging
- not evidence of global unavailability

Examples:

- `codeagent-wrapper` completed without output
- capacity skip
- agent did not satisfy an execution convention and the gate later blocks

Effect:

- record and display
- write timeline evidence
- do **not** trigger `failed_gate`
- do **not** by themselves imply automatic flow blocking

### 2. Execution Outcome

Execution outcome answers:
**Did the role execution satisfy its contract?**

This is separate from severity.

The canonical outcomes are:

- `contract_satisfied`
- `contract_deviated`
- `execution_failed`

Examples:

- agent changed state and produced required refs:
  `contract_satisfied`
- agent produced no output or missed required refs:
  `contract_deviated`
- execution crashed because the provider timed out repeatedly:
  `execution_failed`

`contract_deviated` is often associated with `WARNING`, not necessarily `ERROR`.

### 3. Flow State

Flow state answers:
**What should happen to this workflow now?**

Key rule:

- `blocked` is a normal orchestration state
- `blocked` is not an error severity
- a flow may become `blocked` with or without any `CRITICAL/ERROR` signal

Examples:

- missing required ref after role completion -> flow becomes `blocked`
- state unchanged after worker run -> flow becomes `blocked`
- dependency missing -> flow becomes `blocked`
- repeated API failures -> system may enter failed gate, and an issue may also end up blocked

## Core Design Rules

### Rule 1: `failed_gate` only models system unavailability

`failed_gate` must only react to:

- `CRITICAL`
- thresholded `ERROR`

It must not react to warning-only execution contract deviations.

### Rule 2: `blocked` is owned by workflow rules, not by error severity

A flow may become blocked because:

- required refs are missing
- state did not change as required
- human intervention is needed
- dependencies are unresolved

These are workflow outcomes. They are not automatically infrastructure failures.

### Rule 3: no-op and no-output are not root-cause errors

`no op` means the agent did not satisfy the expected contract.
That is not itself proof of infrastructure failure.

`codeagent-wrapper` no output should therefore be treated as:

- a `WARNING`
- a timeline event
- a `serve status` diagnostic
- an input to gate diagnostics, not a failed-gate trigger

### Rule 4: severity handling must be table-driven

The runtime must stop relying on prefix-only logic such as:

- "all `E_EXEC_*` count toward threshold"
- "all caught exceptions block the issue"

Instead, each code must resolve through a registry that defines:

- severity
- threshold eligibility
- timeline behavior
- issue action
- gate action

## Target Error Mapping

### Infrastructure failures

| Code | Severity | Threshold Eligible | Intended Meaning |
|------|----------|--------------------|------------------|
| `E_MODEL_NOT_FOUND` | `CRITICAL` | No | configured model does not exist |
| `E_MODEL_PERMISSION` | `CRITICAL` | No | configured model cannot be accessed |
| `E_MODEL_CONFIG` | `CRITICAL` | No | configuration is invalid |
| `E_API_RATE_LIMIT` | `ERROR` | Yes | provider rate limit instability |
| `E_API_TIMEOUT` | `ERROR` | Yes | provider timeout instability |
| `E_API_UNAVAILABLE` | `ERROR` | Yes | provider unavailable |
| `E_API_NETWORK` | `ERROR` | Yes | network failure |
| `E_API_UNKNOWN` | `ERROR` | Yes | unknown provider-side failure |

### Contract and observability signals

| Code | Severity | Threshold Eligible | Intended Meaning |
|------|----------|--------------------|------------------|
| `E_EXEC_NO_OUTPUT` | `WARNING` | No | wrapper returned no useful output |
| `E_CAPACITY_SKIP` | `WARNING` | No | dispatch intentionally skipped due to capacity |

### Current `E_EXEC_*` family

The remaining `E_EXEC_*` codes must be reviewed against the new standard during
implementation rather than inherited by prefix.

Interim decision:

- no `E_EXEC_*` code may trigger `failed_gate` solely because it starts with `E_EXEC_`
- each retained `E_EXEC_*` code must be explicitly assigned one of:
  - `ERROR` for confirmed execution infrastructure failure
  - `WARNING` for contract-deviation or observability-only signal
  - replacement by a workflow block reason rather than an error code

## Runtime Handling Contract

Every runtime signal must map to a handling contract with these fields:

- `severity`
- `counts_toward_threshold`
- `record_in_error_log`
- `write_timeline_event`
- `issue_action`
- `gate_action`

### Canonical handling matrix

| Severity | Record | Timeline | Issue Action | Gate Action |
|----------|--------|----------|--------------|-------------|
| `CRITICAL` | Yes | Yes | record-only (no automatic flow blocking) | immediate `failed_gate` |
| `ERROR` | Yes | Yes | record-only (no automatic flow blocking) | threshold-based `failed_gate` |
| `WARNING` | Yes | Yes | no automatic flow blocking solely from warning | no gate activation |

Important constraint:

- a warning may coexist with a later workflow `blocked` state
- the warning is not the reason the system failed
- the block reason should come from gate/workflow semantics, not from warning severity alone

## Required Implementation Changes

### 1. Error registry

Introduce a single registry that maps each runtime code to its handling contract.

Minimum fields:

- `code`
- `severity`
- `counts_toward_threshold`
- `write_timeline_event`
- `issue_action`
- `description`

### 2. Error tracking

`error_tracking` must track severity-aware records.

Required changes:

- threshold counters must only include threshold-eligible `ERROR`
- warning records must be queryable and visible
- status output must separate warnings from errors

### 3. Failed gate

`failed_gate` must stop using `API + EXEC prefix` logic.

Required behavior:

- immediate block on `CRITICAL`
- threshold block on configured `ERROR`
- ignore warning-only signals

### 4. Codeagent execution path

The execution path must stop assuming "exception => block issue".

Required behavior:

- classify via registry-backed severity/disposition
- record warning diagnostics without automatically failing issue state
- emit clearer timeline events for contract deviations and warnings

### 5. No-op gate diagnostics

The no-op gate remains the authority for contract satisfaction.

Required improvements:

- clearer block reasons
- explicit distinction between contract deviation and infrastructure failure
- link timeline diagnostics to the gate decision when possible

## Migration Strategy

### Phase 1: Establish semantics

1. write the new standard
2. rewrite this design spec
3. create an execution guide tied to the current codebase

### Phase 2: Introduce registry and severity-aware tracking

1. add `ErrorSeverity`
2. add error registry metadata
3. make `error_tracking` threshold-aware by registry, not prefix

### Phase 3: Refactor execution handling

1. refactor `codeagent_runner`
2. separate warning timeline events from hard-failure issue actions
3. stop treating `E_EXEC_NO_OUTPUT` as a blocking error

### Phase 4: Refactor failed gate and status surfaces

1. update `failed_gate`
2. update `serve status`
3. update timeline/status wording so warnings and blocked flows are not presented as system failures

### Phase 5: Reclassify remaining execution signals

1. review each retained `E_EXEC_*`
2. move contract-only signals to warning or block reasons
3. keep only true infrastructure failures as `ERROR`

## Success Criteria

1. `E_EXEC_NO_OUTPUT` no longer causes issue failure or failed-gate thresholding by itself.
2. `serve status` shows warnings separately from critical/error counts.
3. `flow timeline` records warning diagnostics without mislabeling them as system failures.
4. `failed_gate` only reacts to configuration unavailability and thresholded infrastructure instability.
5. `blocked` is explicitly treated and rendered as a workflow state, not as an error class.

## References

- `docs/standards/error-handling.md`
- `docs/standards/vibe3-noop-gate-boundary-standard.md`
- `docs/standards/v3/orchestra-runtime-standard.md`
