#!/usr/bin/env bats
# tests/test_task_render.bats - Rendering and Query tests

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  export HELPER="$BATS_TEST_DIRNAME/test_task_helper.zsh"
}

@test "render: renders shared task overview" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"
  make_task_fixture "$fixture"

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    mkdir -p "'"$fixture"'/wt-test-task"
    cd "'"$fixture"'/wt-test-task"
    vibe_task
  '
  echo "DEBUG STATUS: $status" >&3
  echo "DEBUG OUTPUT: $output" >&3
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe Task Registry Overview" ]]
  [[ "$output" =~ "wt-test-task" ]]
}

@test "render: default view manages task visibility by status" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{
  "schema_version": "v1",
  "tasks": [
    {"task_id":"task-blocked","title":"Blocked Task","status":"blocked"},
    {"task_id":"task-review","title":"Review Task","status":"review"},
    {"task_id":"task-completed","title":"Completed Task","status":"completed"}
  ]
}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task
  '
  [ "$status" -eq 0 ]
  echo "$output" | grep -F "task-blocked"
  echo "$output" | grep -F "task-review"
  ! echo "$output" | grep -F "task-completed"
}

@test "render: vibe_task list supports --status/--source/--keywords filters" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{
  "schema_version": "v2",
  "tasks": [
    {"task_id":"t-issue","title":"Fix issue sync","status":"in_progress","source_type":"issue","source_refs":[],"roadmap_item_ids":[],"issue_refs":[],"related_task_ids":[],"subtasks":[],"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"},
    {"task_id":"t-local","title":"Write docs","status":"todo","source_type":"local","source_refs":[],"roadmap_item_ids":[],"issue_refs":[],"related_task_ids":[],"subtasks":[],"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"},
    {"task_id":"t-blocked","title":"Blocked by API","status":"blocked","source_type":"local","source_refs":[],"roadmap_item_ids":[],"issue_refs":[],"related_task_ids":[],"subtasks":[],"created_at":"2026-03-08T10:00:00+08:00","updated_at":"2026-03-08T10:00:00+08:00"}
  ]
}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task list --status blocked
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "t-blocked" ]]
  [[ ! "$output" =~ "t-local" ]]

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task list --source issue
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "t-issue" ]]
  [[ ! "$output" =~ "t-local" ]]

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task list --keywords blocked
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "t-blocked" ]]
  [[ ! "$output" =~ "t-issue" ]]
}

@test "render: displays framework and source path when present" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{
  "schema_version": "v1",
  "tasks": [
    {
      "task_id": "fw-task",
      "title": "Framework Task",
      "framework": "openspec",
      "source_path": "openspec/changes/fw-task",
      "status": "todo"
    }
  ]
}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "openspec" ]]
  [[ "$output" =~ "openspec/changes/fw-task" ]]
  [[ "$output" =~ "fw-task" ]]
}

@test "render: discovers active openspec changes" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/openspec/changes/active-change"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"
  cat > "$fixture/openspec/changes/active-change/tasks.md" <<'MD'
- [ ] active subtask
MD

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    cd "'"$fixture"'"
    vibe_task -a
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "active-change" ]]
}

@test "render: vibe_task show returns merged task details as json" {
  local fixture; fixture="$(mktemp -d)"
  source "$HELPER"
  make_task_fixture "$fixture"
  cat > "$fixture/vibe/tasks/old-task/task.json" <<'JSON'
{
  "task_id": "old-task",
  "title": "Old Task",
  "description": "Detailed task file",
  "status": "done",
  "subtasks": [
    {"subtask_id":"s1","title":"First","status":"done"}
  ],
  "assigned_worktree": "wt-test-task",
  "next_step": "Done."
}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    mock_git_registry "'"$fixture"'"
    vibe_task show old-task --json
  '
  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.task_id')" = "old-task" ]
  [ "$(echo "$output" | jq -r '.assigned_worktree')" = "wt-test-task" ]
  [ "$(echo "$output" | jq -r '.subtasks | length')" = "1" ]
  [ "$(echo "$output" | jq -r '.description')" = "Detailed task file" ]
}
