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

To enter a new implementation flow with TDD:

```bash
# 1. Create/switch to a new flow in the current worktree
vibe flow new <feature-name> --agent claude

# 2. Bind the current execution record when needed
vibe flow bind <task-id>

# 3. Define tests first (TDD Red Phase)
# run the relevant bats/unit test and confirm it fails

# 4. Implement the minimum change (TDD Green Phase)
# run the same test and confirm it passes

# 5. Review code
vibe flow review

# 6. Create Pull Request
vibe flow pr

# 7. Complete feature (after merge)
vibe flow done
```

This workflow:
- Creates or switches to a dedicated flow / branch in the current worktree
- Keeps task binding explicit through `vibe flow bind`
- Guides you through the TDD cycle
- Uses `wtnew` / `vnew` only when you truly need a separate physical worktree
