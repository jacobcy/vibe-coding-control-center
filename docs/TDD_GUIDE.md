# Tibe Coding TDD Workflow Guide

Following the PRD requirements, all development should follow a standardized Test-Driven Development (TDD) cycle.

## The TDD Cycle

1. **Phase 1: Documents (PRD & Tech Spec)**
   - Define WHAT and HOW.
   - Align documentation before writing any code.

2. **Phase 2: Test Definition (test_*.sh)**
   - Create a test file in the `tests/` directory.
   - Define the expected behavior via code.
   - Run the test and ensure it **FAILS** (Red Phase).

3. **Phase 3: Implementation (code)**
   - Write the minimum amount of code to make the test pass.
   - Run the test and ensure it **PASSES** (Green Phase).

4. **Phase 4: Review & Refactor**
   - Clean up code and documentation.
   - Final review and PR.

## Using `tdd-init.sh`

To start a new feature cycle, use the helper script:
```bash
vibe tdd new <feature-name>
```
Or run directly:
```bash
./scripts/tdd-init.sh <feature-name>
```
This will:
- Create a feature branch.
- Generate a test template in `tests/test_<feature-name>.sh`.
- Provide a starting point for implementation.
