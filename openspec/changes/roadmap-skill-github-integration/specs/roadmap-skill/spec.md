## ADDED Requirements

### Requirement: Scheduler checks version goal on invoke
The scheduler SHALL check if a version goal exists when invoked via vibe-new.

#### Scenario: No version goal defined
- **WHEN** scheduler is invoked and no version goal is defined
- **THEN** scheduler prompts human to discuss and define the version goal

#### Scenario: Version goal exists
- **WHEN** scheduler is invoked and version goal is defined
- **THEN** scheduler proceeds to assign priority tasks

### Requirement: Scheduler assigns priority tasks
The scheduler SHALL assign the highest priority task from the current version's backlog.

#### Scenario: Assign next priority task
- **WHEN** scheduler has a version goal and backlog exists
- **THEN** scheduler returns the highest priority task to the orchestrator

### Requirement: Issue classification state machine
Issues SHALL be classified into 5 states based on priority and timing.

#### Scenario: P0 urgent issue
- **WHEN** issue is marked as P0 (blocking/urgent)
- **THEN** scheduler assigns it immediately, not bound by version constraints

#### Scenario: Current version
- **WHEN** issue is classified as current version
- **THEN** scheduler assigns it based on priority within the version

#### Scenario: Next version
- **WHEN** issue is classified as next version
- **THEN** scheduler keeps it in backlog until current version ends

#### Scenario: Deferred
- **WHEN** issue is classified as deferred
- **THEN** scheduler keeps it in pending discussion list

#### Scenario: Rejected
- **WHEN** issue is rejected
- **THEN** scheduler excludes it from consideration

### Requirement: Version cycle management
Scheduler SHALL manage version transitions automatically.

#### Scenario: Version ends
- **WHEN** current version is marked as complete
- **THEN** scheduler confirms next version goal and re-evaluates pending issues

#### Scenario: Re-evaluate pending issues
- **WHEN** version cycle completes
- **THEN** scheduler decides for each pending issue: include in next version / continue deferring / reject

### Requirement: Changelog generation
The system SHALL generate changelog based on completed tasks.

#### Scenario: Major feature completed
- **WHEN** task marked as major feature is completed
- **THEN** version number increases by 0.1

#### Scenario: Minor feature completed
- **WHEN** task marked as minor feature is completed
- **THEN** version number increases by 0.01
