# Spec: Worktree-Aware Path Resolution

## ADDED Requirements

### Requirement: Dynamic Git Directory Detection
The system SHALL resolve the git directory path dynamically using `git rev-parse --git-dir` instead of hardcoding `.git` paths.

#### Scenario: Main repository context
- **WHEN** a vibe command is executed in the main repository
- **THEN** the system SHALL resolve `.git/vibe` using `git rev-parse --git-dir` which returns `.git`
- **AND** all vibe state files SHALL be accessible at `.git/vibe/`

#### Scenario: Worktree context
- **WHEN** a vibe command is executed in a git worktree
- **THEN** the system SHALL resolve the git directory using `git rev-parse --git-dir`
- **AND** the resolved path SHALL point to the main repository's git directory (e.g., `/path/to/main/.git/worktrees/<worktree-name>`)
- **AND** all vibe state files SHALL be accessible at the resolved path plus `/vibe/`

#### Scenario: Bare repository context
- **WHEN** a vibe command is executed in a bare repository
- **THEN** the system SHALL resolve the git directory using `git rev-parse --git-dir`
- **AND** vibe state SHALL be stored relative to the resolved git directory

### Requirement: Backward Compatibility
The system SHALL maintain backward compatibility with existing vibe state stored at `.git/vibe/` in main repositories.

#### Scenario: Existing state access
- **WHEN** a user upgrades to this version in a main repository
- **THEN** existing `.git/vibe/` state SHALL remain accessible
- **AND** no migration or manual intervention SHALL be required

### Requirement: Performance
The system SHALL cache the git directory path for the duration of a shell session to avoid repeated subprocess calls.

#### Scenario: Path caching
- **WHEN** multiple vibe commands are executed in the same shell session
- **THEN** the git directory path SHALL be computed once and cached
- **AND** subsequent commands SHALL reuse the cached value

#### Scenario: Cache invalidation
- **WHEN** the user changes to a different repository or worktree
- **THEN** the cached path SHALL be invalidated and recomputed
