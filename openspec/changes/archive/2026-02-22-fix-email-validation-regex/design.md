## Context

The current `validate_email` function uses a basic regex that is too permissive. There is also a `validate_email_strict` function, but `validate_email` is the primary one used.

## Goals / Non-Goals

**Goals:**
- Make `validate_email` strict enough for production use.
- Reject common invalid email formats.
- Add comprehensive test coverage.

**Non-Goals:**
- Implement full RFC compliance (too complex for shell regex).
- Verify email existence (requires network).

## Decisions

### Decision 1: Use Enhanced Regex

We will replace the existing regex with a more robust one that:
- Disallows starting/ending with dots.
- Disallows consecutive dots.
- Requires valid TLD.

### Decision 2: Add Dedicated Test Script

Since the existing tests are commented out inside `lib/email_validation.sh`, we will move them to a proper test script `tests/test_email_validation.sh` that runs on CI.
