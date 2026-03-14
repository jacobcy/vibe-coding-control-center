# Spec: Vibe Task Runtime (Modified)

## MODIFIED Requirements

### Requirement: Branch Inference in bind-current
The system SHALL automatically infer and persist the current branch when `--bind-current` is used, eliminating the need for explicit branch specification.

#### Scenario: Auto-detect current branch
- **WHEN** user runs `vibe task update <task-id> --bind-current`
- **THEN** the system SHALL detect the current git branch using `git branch --show-current`
- **AND** the detected branch SHALL be persisted to `runtime_branch` field
- **AND** no explicit `--branch` argument SHALL be required

#### Scenario: Branch already specified
- **WHEN** user runs `vibe task update <task-id> --bind-current --branch <branch>`
- **THEN** the system SHALL use the explicitly provided branch
- **AND** SHALL verify it matches the current branch
- **AND** SHALL fail with error if branches don't match

### Requirement: Binding Conflict Prevention
The system SHALL prevent binding a branch that is already bound to another active task, enforcing branch exclusivity.

#### Scenario: Detect conflicting binding
- **WHEN** user attempts to bind a branch already bound to another active task
- **THEN** the system SHALL fail with error containing:
  - Conflicting task ID
  - Conflicting task status
  - Branch name
  - Worktree path (if available)
- **AND** SHALL provide recovery hint (switch branches or clean up old binding)

#### Scenario: Allow rebinding inactive tasks
- **WHEN** a branch is bound to a task with status `done` or `archived`
- **THEN** the system SHALL allow rebinding to a new task
- **AND** SHALL automatically clear the old binding

### Requirement: Runtime Branch Persistence
The system SHALL persist the `runtime_branch` and `pr_ref` fields atomically to prevent state drift.

#### Scenario: Atomic state update
- **WHEN** binding or updating runtime metadata
- **THEN** the system SHALL write to a temporary file first
- **AND** SHALL rename temp file to final location atomically
- **AND** concurrent reads SHALL not see partial updates

#### Scenario: State recovery
- **WHEN** the system loads task runtime state
- **THEN** missing `runtime_branch` or `pr_ref` fields SHALL default to null
- **AND** SHALL not cause loading failures
