# capability-registry Specification

## ADDED Requirements

### Requirement: 能力注册
The system SHALL allow capability modules to register themselves with metadata including name, version, and dependencies.

#### Scenario: Register new capability
- **WHEN** a capability module calls `register_capability` with name "check" and version "1.0"
- **THEN** system adds the capability to the registry with provided metadata

#### Scenario: Register duplicate capability
- **WHEN** attempting to register a capability with a name that already exists
- **THEN** system logs warning and refuses to register duplicate

### Requirement: 能力发现
The system SHALL provide a mechanism to discover available capabilities by name or by feature.

#### Scenario: Discover by name
- **WHEN** system queries registry for capability named "check"
- **THEN** registry returns the check capability module and its metadata

#### Scenario: Discover by feature
- **WHEN** system queries registry for capabilities supporting "git-workflow"
- **THEN** registry returns all capabilities that declare support for git-workflow

### Requirement: 能力调用
The system SHALL provide a unified interface to invoke registered capabilities with proper error handling.

#### Scenario: Invoke capability successfully
- **WHEN** system invokes a registered capability with valid arguments
- **THEN** capability executes and returns result

#### Scenario: Invoke non-existent capability
- **WHEN** system attempts to invoke a capability that is not registered
- **THEN** system returns error indicating capability not found
