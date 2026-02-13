# Workflow: Rotate Task

**Goal**: Quickly switch to a new task within an existing worktree, preserving uncommitted work.

## Trigger
- User wants to start a new task in the same environment.
- User wants to rename the current task/branch but keep changes.
- User wants to discard the current branch history but keep the working directory state for a new attempt.

## Command
`vibe flow rotate <new-task-name>`

## Process
1. **Validation**:
   - Ensure execution within a worktree.
   - Ensure a new task name is provided.

2. **Save State**:
   - `git stash push -m "Rotate to <new-task>"` to save uncommitted changes (index and working tree).

3. **Reset Environment**:
   - Record current branch name (`OLD_BRANCH`).
   - Fetch `origin/main` to ensure latest base.
   - Create and switch to new branch: `git checkout -b <new-task> origin/main`.

4. **Cleanup**:
   - Delete the old branch: `git branch -D <OLD_BRANCH>`.
     - *Note*: This forces deletion, assuming the user is done with the old task context.

5. **Restore State**:
   - Apply the stashed changes: `git stash pop`.
   - Result: New branch with clean history, containing the previously uncommitted work.

## Usage Example
```bash
# In worktree /.../wt-claude-feature-a
# Current branch: feature-a (with WIP changes)

vibe flow rotate feature-b

# Result:
# Branch: feature-b (based on main)
# Changes: WIP changes from feature-a are applied here
# Branch feature-a is deleted
```
