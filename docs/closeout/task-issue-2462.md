# Closeout Directive: task/issue-2462

## Context

Issue #2462 has passed review and is ready for PR creation and publishing.

## Current State

- **Branch**: task/issue-2462
- **Commit**: 89b3603a (refactor(arch): break config → clients dependency cycle)
- **Status**: Review PASSED, ready for PR
- **Target**: main branch

## Publish Instructions

### Step 1: Verify Clean Working Tree

```bash
git status
# Expected: nothing to commit, working tree clean
```

### Step 2: Create PR

Use `vibe-commit` skill to create PR:

```bash
/vibe-commit
```

The skill will:
1. Push branch to remote
2. Create PR with proper title and description
3. Target main branch
4. Preserve issue labels

**Expected PR Content**:
- Title: `refactor(arch): break config → clients dependency cycle (#2462)`
- Body: Should include:
  - Summary: Moved git utilities to utils module to break dependency cycle
  - Changes: 5 source files, 4 test files
  - Verification: 188 tests pass, zero config→clients imports, mypy/ruff clean
  - Backward compatibility: Re-exports preserved

### Step 3: Verify PR Created

```bash
gh pr list --head task/issue-2462 --json number,state,url
# Expected: 1 open PR
```

### Step 4: Update Issue Comment

After PR creation, comment on issue:

```bash
gh issue comment 2462 --body "[executor] PR created: #<PR_NUMBER>

All verification passed. Ready for human review and merge."
```

## Cleanup Mode

- **Mode**: preserve (flow reached successful completion)
- **Reason**: Review PASSED, PR should be created
- **Keep flow record**: Yes (for historical reference)

## PR Verification Checklist

After PR creation, verify:
- [ ] PR title matches commit message
- [ ] PR body contains summary and verification
- [ ] Target branch is main
- [ ] Labels preserved (vibe-task, type/refactor, scope/python, roadmap/p2, tech-debt)
- [ ] CI checks triggered (pytest, mypy, ruff)

## Notes

- Commit already exists (89b3603a), no new commit needed
- Working tree should be clean
- PR should target main branch (not the base branch used for diff)
