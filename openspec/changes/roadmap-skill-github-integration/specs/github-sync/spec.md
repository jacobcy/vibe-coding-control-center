## ADDED Requirements

### Requirement: Task sync supports GitHub provider
The task sync command SHALL support `--provider github` to fetch issues from GitHub.

#### Scenario: Sync from GitHub
- **WHEN** user runs `vibe task sync --provider github --repo owner/repo --label vibe-task`
- **THEN** system fetches open issues matching label and adds to roadmap candidate pool

#### Scenario: Dry run sync
- **WHEN** user runs `vibe task sync --provider github --dry-run`
- **THEN** system displays what would be synced without making changes

### Requirement: Task sync supports issue linking
The system SHALL support binding local tasks to GitHub issues.

#### Scenario: Link task to issue
- **WHEN** user runs `vibe task link <task-id> --issue 123 --repo owner/repo`
- **THEN** system stores issue reference in task metadata

#### Scenario: Unlink task from issue
- **WHEN** user runs `vibe task unlink <task-id>`
- **THEN** system removes issue reference from task metadata

### Requirement: GitHub sync handles conflicts
The sync process SHALL handle conflicts between local and remote states.

#### Scenario: Issue closed remotely
- **WHEN** GitHub issue is closed and sync runs
- **THEN** system updates local task status to completed

#### Scenario: Title changed remotely
- **WHEN** GitHub issue title changes and sync runs
- **THEN** system updates local task title to match remote
