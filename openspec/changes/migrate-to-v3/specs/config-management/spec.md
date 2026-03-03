# config-management Specification

## ADDED Requirements

### Requirement: 配置加载
The system SHALL load configuration from YAML files with support for environment-specific overrides.

#### Scenario: Load default config
- **WHEN** system starts with no environment specified
- **THEN** system loads config/default.yaml

#### Scenario: Load environment-specific config
- **WHEN** VIBE_ENV is set to "production"
- **THEN** system loads config/environments/production.yaml overriding default values

### Requirement: 配置验证
The system SHALL validate configuration values against schema before use.

#### Scenario: Valid configuration
- **WHEN** configuration file contains valid values matching schema
- **THEN** system accepts configuration and proceeds

#### Scenario: Invalid configuration
- **WHEN** configuration file contains invalid values
- **THEN** system reports validation errors and refuses to start

### Requirement: 敏感信息处理
The system SHALL handle sensitive configuration (API keys, tokens) via environment variables rather than config files.

#### Scenario: Read sensitive value
- **WHEN** configuration references a sensitive value like "${API_KEY}"
- **THEN** system reads the value from environment variable API_KEY

#### Scenario: Missing sensitive value
- **WHEN** environment variable for sensitive value is not set
- **THEN** system reports error indicating missing required environment variable
