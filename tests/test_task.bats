#!/usr/bin/env bats

setup() {
  export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
}

make_task_fixture() {
  local fixture="$1"
  local worktree_path="$fixture/wt-claude-refactor"

  mkdir -p "$fixture/vibe/tasks/old-task" "$fixture/vibe/tasks/2026-03-02-rotate-alignment" "$worktree_path"
  cat > "$fixture/vibe/worktrees.json" <<JSON
{"schema_version":"v1","worktrees":[{"worktree_name":"wt-claude-refactor","worktree_path":"$worktree_path","branch":"claude/old-task","current_task":"old-task","status":"active","dirty":false}]}
JSON
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"old-task","title":"Old Task","status":"done","current_subtask_id":null,"assigned_worktree":"wt-claude-refactor","next_step":"Done."},{"task_id":"2026-03-02-rotate-alignment","title":"Rotate Workflow Refinement","status":"todo","current_subtask_id":null,"assigned_worktree":null,"next_step":"Start here."}]}
JSON
  printf '%s\n' '{"task_id":"old-task","title":"Old Task","status":"done","subtasks":[],"assigned_worktree":"wt-claude-refactor","next_step":"Done."}' > "$fixture/vibe/tasks/old-task/task.json"
  printf '%s\n' '{"task_id":"2026-03-02-rotate-alignment","title":"Rotate Workflow Refinement","status":"todo","subtasks":[],"assigned_worktree":null,"next_step":"Start here."}' > "$fixture/vibe/tasks/2026-03-02-rotate-alignment/task.json"
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

@test "vibe_task list reuses shared task overview output" {
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
    vibe_task list
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe Task Overview" ]]
  [[ "$output" =~ "wt-claude-refactor" ]]
}

@test "vibe_task add help prints usage" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    vibe_task add --help
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage: vibe task add" ]]
}

@test "vibe_task add creates registry entry and task source" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task add 2026-03-03-new-task --title "New Task" --next-step "Start here."
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-03-new-task") | .title' "$fixture/vibe/registry.json")" = "New Task" ]
  [ -f "$fixture/vibe/tasks/2026-03-03-new-task/task.json" ]
}

@test "vibe_task update help prints usage" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    vibe_task update --help
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage: vibe task update <task-id>" ]]
}

@test "vibe_task remove help prints usage" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    vibe_task remove --help
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage: vibe task remove <task-id>" ]]
}

@test "vibe_task remove deletes unbound task metadata" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task remove 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ "$(jq '[.tasks[] | select(.task_id=="2026-03-02-rotate-alignment")] | length' "$fixture/vibe/registry.json")" = "0" ]
  [ ! -e "$fixture/vibe/tasks/2026-03-02-rotate-alignment/task.json" ]
}

@test "vibe_task update rejects missing required fields" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    vibe_task update 2026-03-02-cross-worktree-task-registry
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "No update fields provided" ]]
}

@test "vibe_task update writes status to registry" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.name" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-name"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.email" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-email"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --status planning
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .status' "$fixture/vibe/registry.json")" = "planning" ]
}

@test "vibe_task update validates task before mutating git identity" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.name" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-name"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.email" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-email"; return 0; fi
      return 1
    }
    vibe_task update missing-task --agent codex
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Task not found" ]]
  [ ! -e "$fixture/git-user-name" ]
  [ ! -e "$fixture/git-user-email" ]
}

@test "vibe_task update writes next step to registry" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --next-step "Write tests first."
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .next_step' "$fixture/vibe/registry.json")" = "Write tests first." ]
}

@test "vibe_task update keeps task source file aligned with registry fields" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --bind-current --next-step "Synced step."
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .next_step' "$fixture/vibe/registry.json")" = "Synced step." ]
  [ "$(jq -r '.next_step' "$fixture/vibe/tasks/2026-03-02-rotate-alignment/task.json")" = "Synced step." ]
  [ "$(jq -r '.assigned_worktree' "$fixture/vibe/tasks/2026-03-02-rotate-alignment/task.json")" = "wt-claude-refactor" ]
}

@test "vibe_task update bind-current syncs worktree binding and local cache" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --bind-current --next-step "Stay in this worktree."
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .assigned_worktree' "$fixture/vibe/registry.json")" = "wt-claude-refactor" ]
  [ "$(jq -r '.worktrees[] | select(.worktree_name=="wt-claude-refactor") | .current_task' "$fixture/vibe/worktrees.json")" = "2026-03-02-rotate-alignment" ]
  [ "$(jq -r '.task_id' "$fixture/wt-claude-refactor/.vibe/current-task.json")" = "2026-03-02-rotate-alignment" ]
  [ "$(jq -r '.current_task' "$fixture/wt-claude-refactor/.vibe/session.json")" = "2026-03-02-rotate-alignment" ]
  grep -F "task: 2026-03-02-rotate-alignment" "$fixture/wt-claude-refactor/.vibe/focus.md"
}

@test "vibe_task update bind-current preserves string current_subtask_id in session cache" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"
  tmp_registry="$(mktemp)"
  jq '.tasks |= map(if .task_id=="2026-03-02-rotate-alignment" then .current_subtask_id="subtask-1" else . end)' "$fixture/vibe/registry.json" > "$tmp_registry"
  mv "$tmp_registry" "$fixture/vibe/registry.json"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --bind-current
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.current_subtask_id' "$fixture/wt-claude-refactor/.vibe/session.json")" = "subtask-1" ]
}

@test "vibe_task update writes branch for the current worktree" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --bind-current --branch claude/2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.worktrees[] | select(.worktree_name=="wt-claude-refactor") | .branch' "$fixture/vibe/worktrees.json")" = "claude/2026-03-02-rotate-alignment" ]
}

@test "vibe_task update sets allowed agent and git identity" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.name" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-name"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.email" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-email"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --agent codex --bind-current
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .agent' "$fixture/vibe/registry.json")" = "codex" ]
  [ "$(cat "$fixture/git-user-name")" = "codex" ]
  [ "$(cat "$fixture/git-user-email")" = "codex@vibe.coding" ]
}

@test "vibe_task update rejects unknown agent without force" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --agent "Foo Bar" --bind-current
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unsupported agent" ]]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .agent // empty' "$fixture/vibe/registry.json")" = "" ]
}

@test "vibe_task update force-allows custom agent and slugifies email" {
  local fixture
  fixture="$(mktemp -d)"
  make_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then echo true; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.name" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-name"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.email" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-email"; return 0; fi
      return 1
    }
    vibe_task update 2026-03-02-rotate-alignment --agent "Foo Bar" -f --bind-current
  '

  [ "$status" -eq 0 ]
  [ "$(jq -r '.tasks[] | select(.task_id=="2026-03-02-rotate-alignment") | .agent' "$fixture/vibe/registry.json")" = "Foo Bar" ]
  [ "$(cat "$fixture/git-user-name")" = "Foo Bar" ]
  [ "$(cat "$fixture/git-user-email")" = "foo-bar@vibe.coding" ]
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
