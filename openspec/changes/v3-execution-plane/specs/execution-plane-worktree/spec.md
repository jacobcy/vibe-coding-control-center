## ADDED Requirements

### Requirement: Worktree creation with standardized naming
The system SHALL create git worktrees with standardized naming convention `wt-<owner>-<task-slug>`.

#### Scenario: Create worktree with valid name
- **WHEN** user creates worktree for task "add-user-auth" with owner "claude"
- **THEN** system creates worktree named "wt-claude-add-user-auth"

#### Scenario: Handle naming conflict with auto-suffix
- **WHEN** user creates worktree "wt-claude-add-user-auth" but it already exists
- **THEN** system creates worktree with auto-generated suffix "wt-claude-add-user-auth-a1b2"

### Requirement: Worktree naming validation
The system SHALL validate worktree names against the naming convention before creation.

#### Scenario: Reject invalid worktree name
- **WHEN** user attempts to create worktree with invalid name format
- **THEN** system rejects creation and displays naming convention help

### Requirement: Worktree listing and query
The system SHALL provide ability to list all worktrees and query by owner or task.

#### Scenario: List all worktrees
- **WHEN** user runs worktree list command
- **THEN** system displays all worktrees with owner, task-slug, and path

#### Scenario: Query worktrees by owner
- **WHEN** user queries worktrees for owner "claude"
- **THEN** system displays only worktrees starting with "wt-claude-"

### Requirement: Worktree cleanup with safety checks
The system SHALL provide safe worktree removal with confirmation prompts.

#### Scenario: Remove worktree with confirmation
- **WHEN** user removes worktree "wt-claude-add-user-auth"
- **THEN** system prompts for confirmation before deletion

#### Scenario: Force remove without confirmation
- **WHEN** user removes worktree with `--force` flag
- **THEN** system removes worktree immediately without prompt

### Requirement: Worktree validation
The system SHALL validate worktree integrity and git status.

#### Scenario: Validate healthy worktree
- **WHEN** user validates worktree "wt-claude-add-user-auth"
- **THEN** system checks git status, branch tracking, and working directory cleanliness

#### Scenario: Detect corrupted worktree
- **WHEN** user validates worktree with git corruption
- **THEN** system reports corruption and suggests recovery steps
