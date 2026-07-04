# Feature Specification: Observability and Audit Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

The implemented observability package provides loguru setup, filesystem event-log helpers, degraded-mode state, trace configuration/decorator access, and a reserved in-memory audit placeholder. The placeholder is not the persistence layer for governance audit artifacts.

## User Scenarios & Testing

### Scenario 1 - Structured and classified event logs

`setup_logging()` configures logging. `append_governance_event`, `append_orchestra_event`, `append_supervisor_event`, and the related path helpers write domain-specific filesystem logs below the repository-aware runtime log root.

### Scenario 2 - Degraded mode

`get_degraded_manager()` returns the module singleton used to publish cross-module degraded/recovered state. It records availability state; it does not automatically provide every caller with an alternate read-only implementation.

### Scenario 3 - Method tracing

`trace_method` is resolvable through the module lazy map, while `set_trace_min_ms` and `set_trace_max_lines` configure filtering. `trace_method` is currently missing from `observability.__all__`, so wildcard/public-contract metadata is inconsistent with lazy attribute access.

### Scenario 4 - Reserved audit placeholder

`AuditLogger` has an in-memory `_entries` list and `record_action(action, user, resource, changes, metadata)`. `AuditEntry` is a mutable dataclass with `timestamp`, `action`, `user`, `resource`, `changes`, and `metadata`. The module explicitly says `RESERVED - Not yet implemented`; there is no `log()` API, persistence, query interface, or production consumer.

## Requirements

- **FR-001**: repository-aware log helpers MUST anchor shared logs at the resolved main/common repository location rather than arbitrary caller CWD.
- **FR-002**: governance, orchestra, supervisor, tick, issue, scan, and dry-run paths MUST remain distinct helpers where implemented.
- **FR-003**: event append functions MUST be described as filesystem logging utilities, not as transactional audit persistence.
- **FR-004**: degraded mode MUST expose the shared manager/reason API; callers remain responsible for their concrete fail-closed/fallback behavior.
- **FR-005**: `trace_method`, minimum-duration filtering, and maximum-line configuration MUST reflect `trace_method.py` and the current lazy export map.
- **FR-006**: `AuditLogger` MUST be described as a reserved in-memory placeholder. The baseline MUST NOT claim immutability, durable storage, a `log()` method, or governance-chain consumption.
- **FR-007**: observability public-export inconsistency for `trace_method` MUST be tracked as a code gap.
- **FR-008**: governance audit semantics and YAML/Markdown ledgers belong to spec 005, not to the reserved `AuditLogger` placeholder.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3277](https://github.com/jacobcy/vibe-coding-control-center/pull/3277) | Anchored temp/log paths at the main repository root. |
| [#3197](https://github.com/jacobcy/vibe-coding-control-center/pull/3197) | Restructured orchestra logs and added supervisor logs. |
| [#3196](https://github.com/jacobcy/vibe-coding-control-center/pull/3196) | Added event-log highlighting for key events. |
| [#2503](https://github.com/jacobcy/vibe-coding-control-center/pull/2503) | Tightened public export shape to callable/type values. |
| [#1999](https://github.com/jacobcy/vibe-coding-control-center/pull/1999) | Moved orchestra logging APIs into observability. |

## Known gaps and tracking

| Gap | Classification |
|---|---|
| `trace_method` is in `_LAZY_IMPORTS` but omitted from `__all__`. | [#3305](https://github.com/jacobcy/vibe-coding-control-center/issues/3305) |
| `AuditLogger` is publicly exported but explicitly reserved and unused; implementing it, retaining it, or removing it changes architecture direction. | [#3306](https://github.com/jacobcy/vibe-coding-control-center/issues/3306) (`roadmap/rfc`) |

## Success Criteria

- Audit placeholder fields and method names match source exactly.
- No persistence or immutability is attributed to `AuditLogger`/`AuditEntry`.
- Log-path, degraded-mode, and trace behavior remain independently described.

## Non-goals

- Implementing audit persistence.
- Connecting governance ledgers to `AuditLogger`.
- Fixing the export list in this archive pass.
