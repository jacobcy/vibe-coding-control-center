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

## Using `vibe flow`

To start a new feature with TDD workflow:

```bash
# 1. Start feature workflow (creates worktree, PRD, etc.)
vibe flow start <feature-name> --agent=claude

# 2. Navigate to the worktree
cd ../wt-claude-<feature-name>

# 3. Write specification
vibe flow spec

# 4. Initialize tests (TDD Red Phase)
vibe flow test

# 5. Implement feature (TDD Green Phase)
vibe flow dev

# 6. Review and commit
vibe flow review
```

This workflow:
- Creates a dedicated worktree and branch
- Generates PRD and spec documents
- Creates test template in `tests/test_<feature-name>.sh`
- Guides you through the TDD cycle
- Tracks progress with workflow state
