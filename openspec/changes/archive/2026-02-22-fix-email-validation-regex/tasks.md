## 1. Test Development

- [x] 1.1 Create `tests/test_email_validation.sh` with test cases covering valid and invalid scenarios.
- [x] 1.2 Verify tests fail initially (Red Phase).

## 2. Implementation

- [x] 2.1 Update `validate_email` regex in `lib/email_validation.sh` to handle edge cases.
- [x] 2.2 Remove redundant `validate_email_strict` if covered by new `validate_email`.
- [x] 2.3 Verify tests pass (Green Phase).

## 3. Verify

- [x] 3.1 Run `tests/test_email_validation.sh` and ensure all cases pass.
