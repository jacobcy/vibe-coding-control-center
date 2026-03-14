# Spec: Stacked PR Order Persistence

## ADDED Requirements

### Requirement: Merge Dependency Tracking
The system SHALL track merge dependencies between PRs to preserve stacked PR order across sessions.

#### Scenario: Record dependencies on PR creation
- **WHEN** a PR is created with `vibe flow pr`
- **THEN** the system SHALL record any prerequisite PRs in the PR metadata
- **AND** dependencies SHALL be stored as an array of PR numbers in `merge_dependencies` field

#### Scenario: Load existing dependencies
- **WHEN** the system loads PR state from a previous session
- **THEN** the `merge_dependencies` field SHALL be preserved
- **AND** dependencies SHALL be used to enforce merge order

### Requirement: Dependency Persistence Format
The system SHALL store merge dependencies in `roadmap.json` with a well-defined schema.

#### Scenario: Roadmap schema
- **WHEN** storing PR metadata in roadmap.json
- **THEN** the schema SHALL include:
  ```json
  {
    "prs": {
      "<pr-number>": {
        "url": "https://github.com/...",
        "merge_dependencies": ["<pr-number>", ...]
      }
    }
  }
  ```
- **AND** `merge_dependencies` SHALL be an array (possibly empty)
- **AND** missing field SHALL be treated as empty array

#### Scenario: Backward compatibility
- **WHEN** loading PRs created before this feature
- **THEN** missing `merge_dependencies` field SHALL default to empty array
- **AND** no migration SHALL be required

### Requirement: Merge Order Enforcement
The system SHALL validate merge dependencies before allowing merge operations.

#### Scenario: Unmet dependency check
- **WHEN** user attempts to merge a PR with unmet dependencies
- **THEN** the system SHALL warn about unmerged prerequisite PRs
- **AND** the warning SHALL list all unmerged dependencies
- **AND** the user SHALL have the option to proceed anyway or cancel

#### Scenario: Circular dependency detection
- **WHEN** user creates a PR with circular dependencies
- **THEN** the system SHALL detect the cycle
- **AND** SHALL fail with an error message identifying the cycle
- **AND** the PR SHALL NOT be created

### Requirement: Dependency Updates
The system SHALL support updating dependencies after PR creation.

#### Scenario: Add dependency
- **WHEN** user runs `vibe roadmap dependency add <pr> <depends-on-pr>`
- **THEN** the dependency SHALL be added to the PR's `merge_dependencies` array
- **AND** circular dependency check SHALL be performed
- **AND** changes SHALL be persisted atomically

#### Scenario: Remove dependency
- **WHEN** user runs `vibe roadmap dependency remove <pr> <depends-on-pr>`
- **THEN** the dependency SHALL be removed from the array
- **AND** changes SHALL be persisted atomically
