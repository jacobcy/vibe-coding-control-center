## Why

The current email validation regex in `lib/email_validation.sh` is too permissive. It allows invalid formats like `user@.com`, `user..name@example.com`, or domains starting with dots. This poses a risk for data integrity and user communication.

## What Changes

- Update the regex in `validate_email` function to stricter standards.
- Ensure domains cannot start or end with dots/hyphens.
- Disallow consecutive dots in both local and domain parts.
- Add a dedicated test script `tests/test_email_validation.sh` to verify edge cases.

## Capabilities

### Modified Capabilities
- `email-validation`: Stricter regex validation logic.

## Impact

- `lib/email_validation.sh`: Update regex pattern.
- `tests/test_email_validation.sh`: New test file.
