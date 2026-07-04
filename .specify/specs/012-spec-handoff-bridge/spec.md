# Feature Specification: Spec Artifact Handoff Bridge

**Feature Branch**: `task/issue-3310`
**Created**: 2026-07-04
**Status**: Proposed Feature

**Implementation issue**: [#3310](https://github.com/jacobcy/vibe-coding-control-center/issues/3310)
**Architecture decision**: [ADR-0006](../../../docs/decisions/0006-spec-artifact-handoff-contract.md) (`proposed`)

## Problem

Vibe3 has a flow-level `spec_ref` and a readable `@spec` alias, but spec uses a separate write/validation path from plan/report/audit. The current model also permits a GitHub issue ID to stand in for a spec, validates different ref properties at different lifecycle stages, and responds to a missing historical artifact with destructive flow rebuild guidance.

At the same time, spec-kit and superspec already generate repository artifacts under `.specify/`. Vibe should integrate those artifacts through project-owned extension hooks and the existing Handoff boundary rather than modifying external workflow sources or adding another orchestration system.

## User Scenarios & Testing

### User Story 1 - Publish a canonical spec artifact (P1)

An agent or spec-kit hook records a generated `.specify/specs/<NNN-slug>/spec.md` through the same Handoff surface used for later-stage artifacts. The stored ref is repository-relative and `vibe3 handoff show @spec` resolves the exact file.

**Independent Test**: Create a temporary flow/worktree spec file, record it with `handoff spec`, and verify flow state, event history, display, and `@spec` resolution.

**Acceptance Scenarios**:

1. Given a valid canonical spec file, when it is recorded, then `spec_ref` stores a repository-relative path and a successful handoff event is visible.
2. Given an issue number, URL, absolute path, directory, missing file, or non-canonical spec path, when recording is attempted, then the command returns `UserError` without mutating flow state.
3. Given `flow update --spec`, when a valid spec is supplied, then it delegates to the same writer and produces equivalent state/event semantics.

### User Story 2 - Recover a missing artifact without destroying the scene (P1)

If a previously valid spec/plan/report/audit file disappears, the flow reports an artifact blocker and waits for explicit regeneration or rebinding. It does not rebuild a healthy worktree.

**Independent Test**: Record a valid artifact, remove only the file in a temporary test worktree, run consistency/recovery classification, and verify the result is non-destructive and actionable.

**Acceptance Scenarios**:

1. Given a healthy worktree with a missing recorded artifact, when consistency runs, then it distinguishes artifact repair from physical scene rebuild.
2. Given a role that omits its required output entirely, when no-op validation runs, then the existing role-output blocker remains authoritative.
3. Given a runtime/system exception, when execution fails, then error tracking/FailedGate remains separate from the artifact blocker.

### User Story 3 - Publish external workflow artifacts through adapters (P1)

Project-owned spec-kit extension hooks register generated spec/plan/report/audit artifacts through public Vibe commands. External spec-kit, superspec, and Superpowers sources remain untouched.

**Independent Test**: Validate extension metadata and execute fixture hook commands against a temporary flow, confirming the expected Handoff refs and idempotent events.

**Acceptance Scenarios**:

1. After spec-kit specify, the generated spec is recorded as `spec_ref`.
2. After spec-kit plan, the generated plan is recorded as `plan_ref`.
3. After implementation/review adapters complete, report/audit artifacts are recorded through their canonical commands.
4. Direct superspec commands that bypass core hooks still receive a repository-owned exit instruction to publish their outputs.

### User Story 4 - Automated planning consumes available context (P2)

The task-branch planner remains independent from human workflow selection. It consumes a recorded spec when present, evaluates accepted ADRs, and queries relevant long-term memory when available.

**Independent Test**: Build annotated/dry-run planner prompts for flows with no spec, a valid spec, and an unreadable recorded spec; verify the context and failure boundaries.

**Acceptance Scenarios**:

1. A valid `spec_ref` contributes spec content to automated planning.
2. No `spec_ref` remains legal for issue-only tasks.
3. A recorded but unreadable spec is surfaced as a blocker, not silently ignored.
4. Memory evidence is labeled advisory and cannot override issue/spec/accepted ADR/repository truth.

## Requirements

### Artifact identity and mapping

- **FR-001**: canonical spec files MUST match `.specify/specs/<NNN-slug>/spec.md` and be stored as repository-relative paths.
- **FR-002**: `spec_ref` MUST be unset or reference a canonical spec file; issue IDs, issue URLs, arbitrary absolute paths, directories, and missing files MUST be rejected.
- **FR-003**: task issue identity MUST remain in the issue link / `task_issue_number` model and MUST NOT be copied into `spec_ref`.
- **FR-004**: Handoff canonical mapping MUST include `spec -> spec_ref` alongside `plan -> plan_ref`, `run -> report_ref`, and `review -> audit_ref`.

### Write and validation path

- **FR-005**: `vibe3 handoff spec <path>` MUST be the canonical spec writer.
- **FR-006**: `flow update --spec` MAY remain for compatibility but MUST delegate to the same service operation and produce equivalent state/event semantics.
- **FR-007**: authoritative ref validation MUST happen before mutation and MUST verify existence, regular-file type, worktree containment, prohibited log/shared-store paths, and artifact-specific path constraints.
- **FR-008**: validation failure MUST raise `UserError` and MUST NOT partially update flow state, actors, events, or handoff projections.
- **FR-009**: repeated publication of the same ref MUST be idempotent.

### Consistency and recovery

- **FR-010**: consistency checks MUST include `spec_ref`, `plan_ref`, `report_ref`, and `audit_ref` using one shared resolution contract.
- **FR-011**: a missing historical artifact in an otherwise healthy worktree MUST classify as an artifact repair blocker, not as physical scene damage requiring rebuild.
- **FR-012**: role output absence MUST remain governed by `RoleOutputContract` and the no-op gate.
- **FR-013**: runtime/system failures and FailedGate MUST remain separate from business/artifact blocked state.

### Extension bridge

- **FR-014**: integration MUST use a project-owned spec-kit extension/adapter and MUST NOT modify installed external spec-kit, superspec, or Superpowers sources.
- **FR-015**: core lifecycle hooks MUST publish available spec/plan/report/audit artifacts through public Handoff commands.
- **FR-016**: adapters MUST NOT access `.git/vibe3` directly or decide label/state transitions.
- **FR-017**: direct external skill paths that bypass core hooks MUST have a repository-owned exit contract or bridge command that publishes generated artifacts.
- **FR-018**: hook/exit publication MUST be idempotent when both paths observe the same artifact.

### Automated material consumption

- **FR-019**: automated planner material MUST read a recorded spec before planning and MUST distinguish absent optional spec from unreadable recorded spec.
- **FR-020**: planner ADR recall MUST use available issue/spec semantics and the current accepted ADR snapshot.
- **FR-021**: relevant long-term memory MAY be queried as advisory evidence; unavailable tooling MUST be reported as an evidence limitation rather than fabricated as completed recall.
- **FR-022**: memory MUST NOT override latest human instructions, issue/spec requirements, accepted ADRs, or current repository facts.
- **FR-023**: `dev/*` workflow choice MUST remain independent from the `task/*` automated label-driven role lifecycle.

## Relationships to baseline specs

- Spec 001 owns flow consistency/recovery behavior.
- Spec 003 owns role request enrichment and declarative output contracts.
- Spec 006 owns Handoff artifact kinds, validation, resolution, and event visibility.
- Those baseline specs must be updated only when implementation truth changes; this feature spec defines the target delta.

## Success Criteria

- **SC-001**: all four artifact kinds use one validated, idempotent Handoff write contract.
- **SC-002**: a missing artifact never causes automatic destruction of a healthy worktree.
- **SC-003**: spec-kit/superspec fixture workflows publish artifacts without changes to external source trees.
- **SC-004**: annotated planner prompts prove that valid recorded spec and ADR context is consumed, while optional absence remains supported.
- **SC-005**: issue identity and spec artifact identity are never stored in the same field.
- **SC-006**: targeted tests cover manual/automatic role equivalence, extension metadata/hooks, validation atomicity, recovery classification, and prompt provenance.

## Non-goals

- Requiring `dev/*` human collaboration to use spec-kit, superspec, Superpowers, a spec, or a plan.
- Replacing label-driven automated plan/run/review orchestration.
- Forking or patching external workflow source files.
- Introducing a new memory database or replacing claude-memory.
- Treating current.md or generated handoff projections as truth over SQLite flow/event state.
