## ADDED Requirements

### Requirement: Session recovery by task ID
The system SHALL recover full development context (worktree + tmux session) by task ID within 30 seconds.

#### Scenario: Successful recovery by task ID
- **WHEN** user runs recovery command with task_id "abc123"
- **THEN** system locates execution result, switches to worktree, and attaches to tmux session within 30 seconds

#### Scenario: Recovery when session lost
- **WHEN** user recovers task_id "abc123" but tmux session "claude-add-user-auth" is missing
- **THEN** system recreates session and attaches to existing worktree

#### Scenario: Recovery when both worktree and session lost
- **WHEN** user recovers task_id "abc123" but both worktree and session are missing
- **THEN** system reports error with manual recovery instructions

### Requirement: Session recovery by worktree hint
The system SHALL recover session based on worktree path or name.

#### Scenario: Recovery by worktree path
- **WHEN** user runs recovery with worktree path ".worktrees/wt-claude-add-user-auth"
- **THEN** system switches to worktree and attaches to associated tmux session

#### Scenario: Recovery by worktree name
- **WHEN** user runs recovery with worktree name "wt-claude-add-user-auth"
- **THEN** system locates worktree and attaches to associated session

### Requirement: Session recovery by session hint
The system SHALL recover session directly by session name.

#### Scenario: Recovery by session name
- **WHEN** user runs recovery with session name "claude-add-user-auth"
- **THEN** system attaches to session and switches to associated worktree

#### Scenario: Recovery when session exists but worktree missing
- **WHEN** user recovers session "claude-add-user-auth" but worktree is missing
- **THEN** system reports error with worktree recreation instructions

### Requirement: Recovery state preservation
The system SHALL preserve session state during recovery (working directory, environment variables, shell history).

#### Scenario: Preserve working directory
- **WHEN** user recovers session "claude-add-user-auth"
- **THEN** system restores working directory to last known state

#### Scenario: Preserve environment variables
- **WHEN** user recovers session with custom environment variables
- **THEN** system restores environment variables from execution result

### Requirement: Recovery status reporting
The system SHALL report recovery status and any issues encountered.

#### Scenario: Report successful recovery
- **WHEN** recovery completes successfully
- **THEN** system displays recovered worktree path, session name, and recovery time

#### Scenario: Report partial recovery
- **WHEN** recovery succeeds but with warnings (e.g., session recreated)
- **THEN** system displays warning message with details

#### Scenario: Report failed recovery
- **WHEN** recovery fails completely
- **THEN** system displays error message with manual recovery steps

### Requirement: Recovery history tracking
The system SHALL maintain recovery history for debugging and audit purposes.

#### Scenario: Log recovery attempts
- **WHEN** user runs recovery command
- **THEN** system logs task_id, worktree, session, recovery status, and timestamp to `.agent/recovery-history.log`

#### Scenario: Query recovery history
- **WHEN** user queries recovery history for task_id "abc123"
- **THEN** system displays all recovery attempts with timestamps and outcomes
