## 1. Schema & Data Layer Updates

- [x] 1.1 Update `lib/task_write.sh`: Modify `_vibe_task_write_worktrees` to handle `tasks` array (append/update).
- [x] 1.2 Update `lib/task_write.sh`: Update `_vibe_task_refresh_cache` to include multi-task info in `.vibe/current-task.json` and `session.json`.

## 2. Parameter Alignment (--branch)

- [x] 2.1 Update `lib/flow.sh`: Rename `--base` to `--branch` in `_flow_start`, `_flow_start_worktree`, and `_flow_start_task`.
- [x] 2.2 Update `lib/flow_help.sh`: Update help strings to replace `--base` with `--branch`.
- [x] 2.3 Update `lib/task_actions.sh`: Ensure `_vibe_task_update` and `_vibe_task_add` handle `--branch` correctly if not already.
- [x] 2.4 Update `lib/task_help.sh`: Update task help strings.

## 3. Logical Flow Improvements

- [x] 3.1 Update `lib/flow.sh`: In `_flow_start`, implement logic to bind task to current worktree if already inside a feature worktree and `--task` is provided.
- [x] 3.2 Update `lib/flow_status.sh`: Update `_flow_status` to show all tasks bound to the current worktree.

## 4. UI & Rendering

- [x] 4.1 Update `lib/task_render.sh`: Refactor `_vibe_task_render` to group tasks by worktree.

## 5. Verification

- [x] 5.1 Run `vibe check json` to verify schema integrity.
- [x] 5.2 Test `vibe flow start --task <id>` inside a worktree.
- [x] 5.3 Test `vibe task update --branch <new-branch>`.
