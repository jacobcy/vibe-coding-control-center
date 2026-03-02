#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
}

@test "vibe_task fails outside git repository" {
  run zsh -c '
    cd /tmp
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    vibe_task
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Not in a git repository" ]]
}

@test "vibe_task fails when shared registry is missing" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "registry.json" ]]
}

@test "vibe_task fails when current task is missing from registry" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[{"worktree_name":"wt-claude-refactor","worktree_path":"/tmp/wt-claude-refactor","branch":"refactor","current_task":"missing-task","status":"active","dirty":true}]}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"different-task","title":"Different Task","status":"done","current_subtask_id":null,"next_step":"No-op."}]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Task not found in registry: missing-task" ]]
}

@test "vibe_task renders shared task overview" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[{"worktree_name":"wt-claude-refactor","worktree_path":"/tmp/wt-claude-refactor","branch":"refactor","current_task":"2026-03-02-cross-worktree-task-registry","status":"active","dirty":true}]}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"2026-03-02-cross-worktree-task-registry","title":"Cross-Worktree Task Registry","status":"done","current_subtask_id":null,"next_step":"Review the completed registry design."}]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe Task Overview" ]]
  [[ "$output" =~ "wt-claude-refactor" ]]
  [[ "$output" =~ "task: 2026-03-02-cross-worktree-task-registry" ]]
  [[ "$output" =~ "next step: Review the completed registry design." ]]
}

@test "vibe_task renders clean state when worktree is not dirty" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[{"worktree_name":"wt-clean","worktree_path":"/tmp/wt-clean","branch":"main","current_task":"task-clean","status":"idle","dirty":false}]}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"task-clean","title":"Clean Task","status":"todo","current_subtask_id":null,"next_step":"Start work."}]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "state: idle clean" ]]
}

@test "vibe_task default view includes blocked and review tasks but hides completed ones" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"task-blocked","title":"Blocked Task","status":"blocked","current_subtask_id":null,"next_step":"Resolve blocker."},{"task_id":"task-review","title":"Review Task","status":"review","current_subtask_id":null,"next_step":"Address review comments."},{"task_id":"task-completed","title":"Completed Task","status":"completed","current_subtask_id":null,"next_step":"Done."}]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '

  [ "$status" -eq 0 ]
  echo "$output" | grep -F "task-blocked"
  echo "$output" | grep -F "task-review"
  ! echo "$output" | grep -F "task-completed"
}

@test "vibe_task renders framework and source path fields when present" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"task-fw","title":"Framework Task","framework":"openspec","source_path":"openspec/changes/task-fw","status":"todo","current_subtask_id":null,"next_step":"Continue task."}]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "framework: openspec" ]]
  [[ "$output" =~ "source: openspec/changes/task-fw" ]]
}

@test "vibe_task discovers active openspec changes" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  mkdir -p "$fixture/openspec/changes/active-change"
  mkdir -p "$fixture/openspec/changes/archive"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"
  cat > "$fixture/openspec/changes/active-change/tasks.md" <<'MD'
- [x] done task
- [ ] todo task
MD

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") echo true; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        *) return 1 ;;
      esac
    }
    vibe_task -a
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "active-change" ]]
  [[ "$output" =~ "framework: openspec" ]]
  [[ "$output" =~ "status: in-progress" ]]
}
