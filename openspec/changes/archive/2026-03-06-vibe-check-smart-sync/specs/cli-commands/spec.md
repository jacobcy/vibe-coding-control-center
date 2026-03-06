## ADDED Requirements

### Requirement: vibe-flow-list-with-pr-filter
The `vibe flow list` command SHALL support filtering branches by PR status.

#### Scenario: List branches with PRs
- **WHEN** user runs `vibe flow list --pr`
- **THEN** system SHALL display the 10 most recent branches that have associated PRs

#### Scenario: List branches with keywords
- **WHEN** user runs `vibe flow list --keywords <text>`
- **THEN** system SHALL display branches matching the keyword in name, task title, or PR title

### Requirement: vibe-flow-review-json-output
The `vibe flow review` command SHALL support JSON output for programmatic use.

#### Scenario: Review with JSON output
- **WHEN** user runs `vibe flow review <branch> --json`
- **THEN** system SHALL return PR data in JSON format including: number, title, body, comments, reviews, commits, state, mergedAt

#### Scenario: Review without JSON flag
- **WHEN** user runs `vibe flow review <branch>` without `--json`
- **THEN** system SHALL display human-readable PR status (existing behavior)

### Requirement: vibe-flow-status-include-pr-info
The `vibe flow status` command SHALL display PR information when available.

#### Scenario: Status shows PR info
- **WHEN** user runs `vibe flow status <branch>` and the branch has an associated PR
- **THEN** system SHALL display PR number, state, and merge status

#### Scenario: Status without PR
- **WHEN** user runs `vibe flow status <branch>` and the branch has no PR
- **THEN** system SHALL display "No PR" without error
