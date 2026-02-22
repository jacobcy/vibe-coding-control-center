# validate-email Specification

## Purpose
TBD - created by archiving change fix-email-validation-regex. Update Purpose after archive.
## Requirements
### Requirement: Stricter Email Validation

The `validate_email` function MUST reject emails with invalid structural elements like consecutive dots, starting/ending dots in domain, or missing top-level domain.

#### Scenario: Valid Standard Emails

- **WHEN** validate_email is called with "user@example.com"
- **THEN** it should return 0 (success)

#### Scenario: Invalid Domain Structure

- **WHEN** validate_email is called with "user@.com"
- **THEN** it should return 1 (failure)

#### Scenario: Consecutive Dots

- **WHEN** validate_email is called with "user..name@example.com"
- **THEN** it should return 1 (failure)

#### Scenario: Domain Starts/Ends with Dot

- **WHEN** validate_email is called with ".example.com"
- **THEN** it should return 1 (failure)

