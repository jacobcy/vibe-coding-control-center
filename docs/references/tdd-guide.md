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

## Using `vibe3 flow`

To enter a new implementation flow with TDD:

```bash
# 1. Create a new branch for the feature (use git directly)
git checkout -b <feature-name>

# 2. Register the flow for the current branch
vibe3 flow update --name <feature-name>

# 3. Bind the issue when needed
vibe3 flow bind <issue-number>

# 4. Define tests first (TDD Red Phase)
# run the relevant bats/unit test and confirm it fails

# 5. Implement the minimum change (TDD Green Phase)
# run the same test and confirm it passes

# 6. Review code
# use git diff / PR review tools

# 7. Create Pull Request (use gh directly)
gh pr create

# 8. Complete feature (after merge)
# the flow is auto-completed on PR merge
```

This workflow:
- Uses `git` directly for branch lifecycle (creation, switching)
- Uses `vibe3 flow update` to register flow metadata for the current branch
- Keeps task binding explicit through `vibe3 flow bind`
- Guides you through the TDD cycle
- Uses `wtnew` / `vnew` only when you truly need a separate physical worktree
