# Spec: Flow Merge Workflow (Modified)

## MODIFIED Requirements

### Requirement: Worktree Occupancy Check Before Deletion
The system SHALL check if a branch is still checked out in a worktree before attempting to delete it.

#### Scenario: Branch not in use
- **WHEN** running `vibe flow merge` on a branch not checked out in any worktree
- **THEN** the branch SHALL be deleted after successful merge
- **AND** the deletion SHALL proceed normally

#### Scenario: Branch occupied in worktree
- **WHEN** running `vibe flow merge` on a branch still checked out in a worktree
- **THEN** the system SHALL skip branch deletion
- **AND** SHALL display a warning message containing:
  - Branch name
  - Worktree path
  - Instruction to remove worktree first if desired
- **AND** the merge itself SHALL still complete successfully

#### Scenario: Multiple worktrees
- **WHEN** the branch is checked out in multiple worktrees
- **THEN** all worktree paths SHALL be listed in the warning
- **AND** branch deletion SHALL be skipped

### Requirement: Safe Default Behavior
The system SHALL default to safe behavior (no deletion) when worktree occupancy cannot be determined.

#### Scenario: Worktree check failure
- **WHEN** `git worktree list` command fails
- **THEN** the system SHALL skip branch deletion
- **AND** SHALL warn that occupancy could not be verified
- **AND** SHALL suggest manual verification

#### Scenario: Force deletion flag
- **WHEN** user explicitly provides `--force-delete` flag (future enhancement)
- **THEN** the system SHALL delete the branch regardless of occupancy
- **AND** SHALL warn this is a destructive operation
- **NOTE**: This flag is NOT part of current implementation, only future consideration

### Requirement: Merge Success Independent of Deletion
The system SHALL complete the merge operation successfully even if branch deletion is skipped.

#### Scenario: Merge succeeds, deletion skipped
- **WHEN** the merge completes but deletion is skipped due to occupancy
- **THEN** the merge result SHALL still be valid
- **AND** the feature branch SHALL remain in the repository
- **AND** the user SHALL be able to manually delete it later

#### Scenario: User notification
- **WHEN** branch deletion is skipped
- **THEN** the system SHALL clearly indicate the merge succeeded
- **AND** SHALL separately indicate the deletion was skipped with reason
- **AND** the exit code SHALL reflect merge success (0), not deletion skip
