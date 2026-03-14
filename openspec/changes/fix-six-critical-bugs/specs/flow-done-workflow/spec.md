# Spec: Flow Done Workflow (Modified)

## MODIFIED Requirements

### Requirement: Clean Worktree State After Closeout
The system SHALL ensure the worktree is in a clean state (not detached HEAD) after `vibe flow done` completes.

#### Scenario: Checkout parent branch before cleanup
- **WHEN** user runs `vibe flow done` on a feature branch
- **THEN** the system SHALL identify the parent branch (usually `main` or `master`)
- **AND** SHALL checkout the parent branch before deleting the feature branch
- **AND** the worktree SHALL end in a clean state on the parent branch

#### Scenario: Parent branch detection
- **WHEN** identifying the parent branch
- **THEN** the system SHALL try `git merge-base --fork-point main HEAD`
- **AND** if that fails, SHALL default to `main`
- **AND** SHALL verify the parent branch exists locally

#### Scenario: Parent branch not found
- **WHEN** the parent branch doesn't exist locally
- **THEN** the system SHALL fetch it from remote
- **AND** SHALL checkout the remote tracking branch if needed

### Requirement: Safe Branch Deletion
The system SHALL only delete the feature branch if the worktree is not left in a broken state.

#### Scenario: Successful closeout
- **WHEN** `vibe flow done` completes successfully
- **THEN** the feature branch SHALL be deleted
- **AND** the worktree SHALL be on the parent branch
- **AND** no detached HEAD state SHALL occur

#### Scenario: Deletion failure recovery
- **WHEN** branch deletion fails for any reason
- **THEN** the worktree SHALL still be on the parent branch
- **AND** an error message SHALL explain the failure
- **AND** manual cleanup instructions SHALL be provided

### Requirement: Worktree Occupancy Check
The system SHALL not delete a branch that is still checked out in any worktree.

#### Scenario: Single worktree
- **WHEN** running `vibe flow done` in the only worktree using the branch
- **THEN** the branch deletion SHALL proceed after checkout

#### Scenario: Multiple worktrees
- **WHEN** the branch is checked out in another worktree
- **THEN** the system SHALL warn about the other worktree
- **AND** SHALL skip branch deletion
- **AND** SHALL suggest removing the other worktree first
