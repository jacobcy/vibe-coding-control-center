---
description: Test-Driven Development (TDD) Cycle
---

Follow this workflow to implement new features or fix bugs using TDD.

### 1. Initialize the Cycle
Start by creating a failing test for your feature.
// turbo
```bash
./scripts/vibecoding.sh tdd new <feature-name>
```
*Note: This creates `tests/test_<feature-name>.sh` with a template that is guaranteed to fail.*

### 2. Red Phase: Define Expectations
Edit the newly created test file `tests/test_<feature-name>.sh`.
- Define the desired behavior.
- Add assertions (e.g., check if a function returns expected output or a file exists).
- Run the test to confirm it **FAILS**:
```bash
./tests/test_<feature-name>.sh
```

### 3. Green Phase: Minimum Implementation
Write the minimum amount of code required to make the test pass.
- Implement the logic in `lib/` or `scripts/`.
- Run the test again until it **PASSES**:
```bash
./tests/test_<feature-name>.sh
```

### 4. Refactor Phase: Clean Up
Once the test passes, improve the code quality.
- Remove duplication.
- Improve naming.
- Ensure the test still **PASSES**.

### 5. Final Verification
Run all project tests to ensure no regressions.
```bash
./scripts/test-all.sh
```
