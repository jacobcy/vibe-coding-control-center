# lifecycle-hooks Specification

## ADDED Requirements

### Requirement: 钩子注册
The system SHALL allow capability modules to register lifecycle hooks for specific commands.

#### Scenario: Register before hook
- **WHEN** a capability registers hook_before_check function
- **THEN** system executes this function before the check command runs

#### Scenario: Register after hook
- **WHEN** a capability registers hook_after_commit function
- **THEN** system executes this function after the commit command completes

### Requirement: 钩子执行顺序
The system SHALL execute hooks in a deterministic order when multiple hooks are registered for the same lifecycle point.

#### Scenario: Execute hooks in registration order
- **WHEN** two capabilities register before_check hooks
- **THEN** system executes hooks in the order they were registered

#### Scenario: Hook failure handling
- **WHEN** a before hook fails
- **THEN** system stops execution and does not proceed with command or after hooks

### Requirement: 钩子上下文
The system SHALL provide context information to hooks including command arguments and current state.

#### Scenario: Pass command arguments to hook
- **WHEN** user runs `vibe check --fix`
- **THEN** before_check hook receives arguments ["--fix"]

#### Scenario: Provide state to after hook
- **WHEN** command execution completes
- **THEN** after hook receives execution result and exit code
