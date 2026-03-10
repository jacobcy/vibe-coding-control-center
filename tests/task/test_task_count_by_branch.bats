#!/usr/bin/env bats
# tests/task/test_task_count_by_branch.bats - Test count-by-branch functionality

setup() {
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export HELPER="$BATS_TEST_DIRNAME/test_task_helper.zsh"
}

@test "count-by-branch: returns 0 when no tasks on branch" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[]}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[]}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    _vibe_task_count_by_branch "feature/test"
  '
  [ "$status" -eq 0 ]
  [ "$output" -eq 0 ]
}

@test "count-by-branch: counts tasks correctly for branch with tasks" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{
  "schema_version":"v1",
  "worktrees":[
    {
      "worktree_name":"wt-test",
      "branch":"feature/test",
      "tasks":["task-1","task-2"]
    }
  ]
}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"task-1"},{"task_id":"task-2"}]}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    _vibe_task_count_by_branch "feature/test"
  '
  [ "$status" -eq 0 ]
  [ "$output" -eq 2 ]
}

@test "count-by-branch: counts tasks across multiple worktrees on same branch" {
  local fixture; fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{
  "schema_version":"v1",
  "worktrees":[
    {
      "worktree_name":"wt-test-1",
      "branch":"feature/test",
      "tasks":["task-1"]
    },
    {
      "worktree_name":"wt-test-2",
      "branch":"feature/test",
      "tasks":["task-2","task-3"]
    }
  ]
}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"task-1"},{"task_id":"task-2"},{"task_id":"task-3"}]}
JSON

  run zsh -c '
    source "'"$HELPER"'"
    setup_task_env
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    _vibe_task_count_by_branch "feature/test"
  '
  [ "$status" -eq 0 ]
  [ "$output" -eq 3 ]
}
