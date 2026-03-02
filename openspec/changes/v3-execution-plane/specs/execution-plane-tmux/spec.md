## ADDED Requirements

### Requirement: Tmux session creation with standardized naming
The system SHALL create tmux sessions with standardized naming convention `<agent>-<task-slug>`.

#### Scenario: Create session with valid name
- **WHEN** user creates tmux session for task "add-user-auth" with agent "claude"
- **THEN** system creates session named "claude-add-user-auth"

#### Scenario: Handle session naming conflict
- **WHEN** user creates session "claude-add-user-auth" but it already exists
- **THEN** system attaches to existing session instead of creating new one

### Requirement: Tmux session attachment and switching
The system SHALL allow users to attach to or switch between sessions.

#### Scenario: Attach to existing session
- **WHEN** user attaches to session "claude-add-user-auth"
- **THEN** system switches terminal to the specified session

#### Scenario: Switch between sessions
- **WHEN** user switches from session "claude-add-user-auth" to "claude-fix-bug"
- **THEN** system detaches from current session and attaches to target session

### Requirement: Tmux session kill with safety
The system SHALL provide safe session termination with confirmation.

#### Scenario: Kill session with confirmation
- **WHEN** user kills session "claude-add-user-auth"
- **THEN** system prompts for confirmation before termination

#### Scenario: Force kill without confirmation
- **WHEN** user kills session with `--force` flag
- **THEN** system terminates session immediately without prompt

### Requirement: Tmux session rename
The system SHALL allow renaming sessions while preserving session state.

#### Scenario: Rename session successfully
- **WHEN** user renames session "claude-add-user-auth" to "claude-user-auth-v2"
- **THEN** system updates session name without losing session state

### Requirement: Tmux session recovery
The system SHALL provide session recovery when tmux server restarts or sessions are lost.

#### Scenario: Recover session from execution result
- **WHEN** user runs session recovery command for task_id "abc123"
- **THEN** system reads execution result, recreates session "claude-add-user-auth" if missing

#### Scenario: Recovery with worktree still exists
- **WHEN** user recovers session but worktree "wt-claude-add-user-auth" still exists
- **THEN** system creates new session and attaches to existing worktree

### Requirement: Tmux session listing
The system SHALL list all sessions with their status and associated tasks.

#### Scenario: List all sessions
- **WHEN** user runs session list command
- **THEN** system displays all sessions with agent, task-slug, and attachment status

#### Scenario: List sessions with task context
- **WHEN** user lists sessions with `--task-context` flag
- **THEN** system displays sessions with their associated task IDs and worktrees
