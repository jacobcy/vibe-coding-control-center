---
description: Test-Driven Development (TDD) Cycle
---

Follow this workflow to implement new features or fix bugs using TDD.

### 1. Initialize the Cycle
Use `vibe flow` to start a new feature or bug fix. This will set up the environment and guide you.
```bash
vibe flow
# Select "Start Feature" or "Start Bugfix"
```

### 2. Red Phase: Define Expectations
Create or edit a test file in `tests/`.
- Define the desired behavior.
- Add assertions.
- Run the test to confirm it **FAILS**:
```bash
# Example: ./tests/test_feature.sh
```

### 3. Green Phase: Minimum Implementation
Write the minimum amount of code required to make the test pass.
- Implement logic in `lib/` or `scripts/`.
- Run the test repeatedly until it **PASSES**.

### 4. Refactor Phase: Clean Up
Once the test passes, improve code quality.
- Remove duplication.
- Improve naming.
- Ensure the test still **PASSES**.

### 5. Final Verification
Run all project tests to ensure no regressions.
```bash
./scripts/test-all.sh
```
