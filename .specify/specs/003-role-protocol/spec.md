# Feature Specification: Role Protocol Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

The current role protocol is defined by `src/vibe3/roles/`, `src/vibe3/config/role_policy.py`, execution request/result models, and orchestration transitions. This spec describes declarative role metadata and the runtime builders that consume it.

## User Scenarios & Testing

### Scenario 1 - Label-triggered roles

`LABEL_DISPATCH_ROLES` contains manager, handoff-manager, planner, executor, publish-executor, reviewer, and a blocked pseudo-role used only by qualification. `build_label_dispatch_event()` emits neutral domain intents; handlers enrich execution-specific context later.

### Scenario 2 - Declarative output validation

`RoleDefinition` declares name, registry role, worktree requirement, optional trigger, and output contract. `RoleOutputContract` currently requires `plan_ref` for planner and a verdict for reviewer. The unified no-op gate enforces these outputs after execution.

### Scenario 3 - Manual and automatic execution share builders

Role modules provide request builders used by both label-driven handlers and synchronous/manual command paths. Sync and async execution differ in launch/session handling, not in the meaning of the role output.

## Requirements

- **FR-001**: label dispatch MUST use `TriggerableRoleDefinition.trigger_name` and `trigger_state` rather than a second independent role table.
- **FR-002**: the blocked pseudo-role MUST be handled by qualification and MUST NOT be emitted as a dispatch event.
- **FR-003**: domain intent construction MUST remain neutral; refs, publish mode, backend/model options, and prompt context are added by handler/role builders.
- **FR-004**: planner output MUST include `plan_ref`; reviewer output MUST include `latest_verdict`; the current executor contract MUST NOT be documented as requiring an unconditional artifact ref.
- **FR-005**: role worktree needs MUST use the implemented `WorktreeRequirement` values (`none`, `permanent`, `temporary`).
- **FR-006**: governance and supervisor execution are not label-triggered entries in `LABEL_DISPATCH_ROLES`; their orchestration uses dedicated scan/manual paths.
- **FR-007**: public role imports MUST follow the package barrel contract; internal helper details are not part of this behavioral spec.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#1870](https://github.com/jacobcy/vibe-coding-control-center/pull/1870) | Moved role output contracts into declarative role definitions and unified no-op ref checks. |
| [#2670](https://github.com/jacobcy/vibe-coding-control-center/pull/2670) | Refactored CLI role commands onto the event-driven execution architecture. |
| [#3156](https://github.com/jacobcy/vibe-coding-control-center/pull/3156) | Added the governance decision role/material path outside label-triggered worker roles. |
| [#3143](https://github.com/jacobcy/vibe-coding-control-center/pull/3143) | Added plan/spec/issue provenance to role execution results. |

## Known gaps and tracking

No uncovered role-protocol implementation gap was found in this review. Changes in blocked recovery and dependency re-evaluation are tracked by specs 001/002 and their linked issues rather than duplicated here.

## Success Criteria

- Trigger metadata, request enrichment, output contracts, and worktree needs are described at their actual owners.
- Governance/supervisor paths are not falsely presented as label-triggered worker roles.
- Requirements can be checked against the registry and role-policy tests.

## Non-goals

- Defining prompt content for individual roles.
- Redesigning the orchestration state machine.
- Expanding role output contracts.

## spec 012 touchpoints

Spec 012 (Spec Artifact Handoff Bridge) delivered by #3310-#3313:
- planner role now consumes recorded spec_ref via SpecRefService, distinguishing absent from unreadable (FR-019)
- ADR recall integrated at plan time per vibe-adr-recall low-code procedure (FR-020)
