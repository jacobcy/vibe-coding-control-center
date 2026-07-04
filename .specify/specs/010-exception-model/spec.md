# Feature Specification: Exception Model Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

This baseline describes the implemented exception hierarchy, runtime error-code classification, severity contracts, and transient Git-pattern helper. `docs/standards/error-handling.md` contains a broader aspirational System/User/Batch taxonomy that is not fully implemented; that disagreement is tracked rather than rewritten as code truth.

## User Scenarios & Testing

### Scenario 1 - Typed Vibe errors

`VibeError(message, recoverable)` is the implemented common base. `UserError` marks recoverable input/configuration problems; `SystemError` marks non-recoverable system failures. Concrete exceptions add structured context. Several business/orchestration exceptions inherit directly from `VibeError` with their own recovery semantics.

### Scenario 2 - Runtime severity and FailedGate

`ErrorHandlingContract` maps stable error codes to `WARNING`, `ERROR`, or `CRITICAL`, threshold participation, logging/timeline behavior, issue action, and gate action. FailedGate consumes persisted severity/count state. Runtime severity does not directly set the business blocked reason/label.

### Scenario 3 - Hybrid classification

`classify_error_hybrid()` first maps exception types/names, then falls back to bounded message matching. Unknown values become `E_EXEC_UNKNOWN`. `is_permanent_code_error()` distinguishes selected programming exceptions from transient infrastructure errors for dispatch recording.

### Scenario 4 - Transient Git pattern detection

`is_transient_git_error()` checks a small tuple of production-known retry-safe substrings. It returns a boolean only; it does not map “permission denied” to `SystemError` or “branch not found” to `UserError`.

## Requirements

- **FR-001**: the baseline hierarchy MUST start at `VibeError` and accurately list implemented `UserError`, `SystemError`, direct `VibeError`, and runtime-infrastructure subclasses.
- **FR-002**: `recoverable` MUST be treated as exception metadata; it does not itself implement CLI confirmation or `-y` behavior.
- **FR-003**: `UserError` MUST NOT be documented as owning a universal `-y/--yes` bypass. Individual commands decide whether confirmation or a bypass flag exists.
- **FR-004**: no `BatchError` class exists in the current package; batch continuation/reporting in the standard is desired policy, not an implemented common exception.
- **FR-005**: severity contracts MUST remain orthogonal to business blocked state and MUST describe their actual FailedGate/error-log actions.
- **FR-006**: error-code classification MUST preserve exception-first then string-fallback behavior and return the implemented default for unknown errors.
- **FR-007**: transient Git patterns MUST be documented only as retry-safety detection.
- **FR-008**: the repository currently contains local exception classes outside `vibe3.exceptions`, including direct `Exception`, `RuntimeError`, and `ValueError` subclasses. The baseline MUST NOT claim all layers already use one hierarchy.

## Implemented entities

- `VibeError`, `UserError`, `SystemError`
- concrete user/system/business/orchestration errors exported by `vibe3.exceptions`
- `RuntimeInfrastructureError`, `APIError`, `ModelError`, `DatabaseError`, `GitHubAPIError`
- `ErrorSeverity`, `ErrorHandlingContract`, error-code registry/classifiers
- `TRANSIENT_GIT_ERROR_PATTERNS`, `is_transient_git_error`

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3158](https://github.com/jacobcy/vibe-coding-control-center/pull/3158) | Added AUP rejection classification/retry protection. |
| [#3023](https://github.com/jacobcy/vibe-coding-control-center/pull/3023) | Classified SSH timeout failures as transient Git errors. |
| [#2874](https://github.com/jacobcy/vibe-coding-control-center/pull/2874) | Projected issue failure into the error log. |
| [#2364](https://github.com/jacobcy/vibe-coding-control-center/pull/2364) | Exported `ErrorHandlingContract` through the package API. |

## Known gaps and tracking

The standard's System/User/Batch model, universal bypass language, and “all custom exceptions share the module hierarchy” requirement conflict with current code. Choosing whether to migrate code, revise the standard, or define two explicitly separate taxonomies is a direction decision tracked by [#3307](https://github.com/jacobcy/vibe-coding-control-center/issues/3307) (`roadmap/rfc`).

## Success Criteria

- No nonexistent `BatchError` or Git taxonomy mapper is presented as implemented.
- `-y` behavior remains command-owned.
- Severity/error-code behavior and business block behavior remain separate.
- The documentation/code direction disagreement is linked to an RFC.

## Non-goals

- Implementing the standard's missing taxonomy.
- Moving local exception classes.
- Changing FailedGate thresholds or error codes.
