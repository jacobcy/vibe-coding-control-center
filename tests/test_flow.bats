#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../bin:$PATH"
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  # Source needed libraries for unit tests
  source "$VIBE_ROOT/lib/config.sh"
  source "$VIBE_ROOT/lib/utils.sh"
  source "$VIBE_ROOT/lib/flow.sh"
}

make_flow_task_fixture() {
  local fixture="$1"
  local worktree_dir="${2:-$fixture/wt-claude-refactor}"

  mkdir -p "$fixture/vibe" "$worktree_dir" "$worktree_dir/.vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"2026-03-02-rotate-alignment","title":"Rotate Workflow Refinement","status":"planning","next_step":"Implement flow start."}]}
JSON
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[]}
JSON
}

@test "1. vibe flow help outputs subcommands" {
  run vibe flow help
  [ "$status" -eq 0 ]
  # Check for key parts separately (output has ANSI color codes)
  [[ "$output" =~ "Usage:" ]]
  [[ "$output" =~ "vibe flow" ]]
  [[ "$output" =~ "new" ]]
  [[ "$output" =~ "bind" ]]
  [[ "$output" =~ "done" ]]
  [[ "$output" =~ "status" ]]
  [[ "$output" =~ "list" ]]
  [[ ! "$output" =~ "sync" ]]
  [[ "$output" =~ "review" ]]
  [[ "$output" =~ "pr" ]]
  [[ "$output" =~ "save-unstash" ]]
  [[ ! "$output" =~ "switch" ]]
}

@test "1.1 vibe flow review help points to the supported Codex package" {
  run vibe flow review --help

  [ "$status" -eq 0 ]
  [[ "$output" =~ "@openai/codex" ]]
  [[ ! "$output" =~ "@anthropic/codex" ]]
  [[ "$output" =~ "[<pr-or-branch>|--branch <ref>]" ]]
}

@test "2. vibe flow new without args returns error" {
  run vibe flow new
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Usage: vibe flow new" ]]
}

@test "2.2 _flow_new refuses dirty worktree without --save-unstash" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo "M dirty-file"; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Working directory is not clean" ]]
  [[ "$output" =~ "save-unstash" ]]
}

@test "2.3 _flow_new allows starting a new flow from main" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }

    git() {
      case "$*" in
        "branch --show-current") echo "main"; return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "checkout -b task/next-flow main") echo "CHECKOUT_NEW"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CHECKOUT_NEW" ]]
}

@test "2.4 _flow_new stashes changes and creates a new branch when requested" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo "M dirty-file"; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "stash push -u -m Flow new to task/next-flow: saved WIP") echo "STASHED"; return 0 ;;
        "checkout -b task/next-flow main") echo "CHECKOUT_NEW"; return 0 ;;
        "stash pop") echo "UNSTASHED"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow --branch main --save-unstash
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "STASHED" ]]
  [[ "$output" =~ "CHECKOUT_NEW" ]]
  [[ "$output" =~ "UNSTASHED" ]]
}

@test "2.5 _flow_new rejects same branch name" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }

    git() {
      case "$*" in
        "branch --show-current") echo "task/next-flow"; return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Target branch matches current branch" ]]
}

@test "2.6 _flow_switch re-enters an existing open flow without PR history" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 0; }
    _flow_branch_has_pr() { return 1; }
    _flow_branch_ref() { echo "origin/task/next-flow"; return 0; }
    _flow_update_current_worktree_branch() { echo "RUNTIME_UPDATED"; return 0; }

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "checkout -b task/next-flow origin/task/next-flow") echo "CHECKOUT_EXISTING"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_switch next-flow
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CHECKOUT_EXISTING" ]]
  [[ "$output" =~ "RUNTIME_UPDATED" ]]
}

@test "2.7 _flow_update_current_worktree_branch upserts current worktree when runtime entry is missing" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-codex-runtime-upsert"
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[]}
JSON

  run zsh -c '
    cd "'"$fixture"'/wt-codex-runtime-upsert"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 0
    }
    _flow_update_current_worktree_branch "task/runtime-upsert"
    jq -r ".worktrees[0].worktree_name + \"|\" + .worktrees[0].worktree_path + \"|\" + .worktrees[0].branch + \"|\" + .worktrees[0].status" "'"$fixture"'/vibe/worktrees.json"
  '

  [ "$status" -eq 0 ]
  [ "$output" = "wt-codex-runtime-upsert|$fixture/wt-codex-runtime-upsert|task/runtime-upsert|active" ]
}

@test "2.1 _flow_new rejects legacy --base alias to keep branch semantics explicit" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_new_worktree() { echo "UNEXPECTED_WORKTREE_CALL"; return 0; }
    _flow_new demo --base develop
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown option: --base" ]]
  [[ "$output" =~ "--branch" ]]
  [[ ! "$output" =~ "UNEXPECTED_WORKTREE_CALL" ]]
}

@test "2.8 vibe flow new help no longer describes worktree creation" {
  run vibe flow new --help

  [ "$status" -eq 0 ]
  [[ "$output" =~ "save-unstash" ]]
  [[ ! "$output" =~ "worktree" ]]
}

@test "3. vibe flow status in non-worktree returns error" {
  # Run in a directory that is definitely not a worktree
  cd /tmp
  run vibe flow status
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Not in a worktree" ]]
}

@test "3.1 _flow_show resolves current flow details from runtime state" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-claude-refactor"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[
  {"task_id":"task-main","title":"Main Task","status":"in_progress","next_step":"Gate 4","assigned_worktree":"wt-claude-refactor","agent":"claude","pr_ref":"#42","issue_refs":["#7"]},
  {"task_id":"task-side","title":"Side Task","status":"todo","next_step":"Gate 2","assigned_worktree":"wt-claude-refactor","agent":"claude"}
]}
JSON
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[
  {"worktree_name":"wt-claude-refactor","worktree_path":"FIXTURE_PATH","branch":"task/refactor","current_task":"task-main","tasks":["task-main","task-side"]}
]}
JSON
  perl -0pi -e 's#FIXTURE_PATH#'"$fixture"'/wt-claude-refactor#' "$fixture/vibe/worktrees.json"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="'"$VIBE_ROOT"'/lib"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "task/refactor"; return 0; fi
      if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then echo ""; return 0; fi
      return 0
    }
    _flow_show --json
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ '"feature": "refactor"' ]]
  [[ "$output" =~ '"current_task": "task-main"' ]]
  [[ "$output" =~ '"task_status": "in_progress"' ]]
  [[ "$output" =~ '"pr_ref": "#42"' ]]
  [[ "$output" =~ '"#7"' ]]
}

@test "3.2 _flow_status shows only open flow dashboard entries" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-claude-refactor"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[
  {"task_id":"task-main","title":"Main Task","status":"in_progress","next_step":"Gate 4","assigned_worktree":"wt-claude-refactor","agent":"claude","pr_ref":"#42"},
  {"task_id":"task-main-2","title":"Main Task 2","status":"todo","next_step":"Gate 2","assigned_worktree":"wt-main","agent":"claude"}
]}
JSON
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[
  {"worktree_name":"wt-claude-refactor","branch":"task/refactor","current_task":"task-main","tasks":["task-main"],"status":"active"},
  {"worktree_name":"wt-main","branch":"main","current_task":"task-main-2","tasks":["task-main-2"],"status":"active"},
  {"worktree_name":"wt-missing","branch":"task/ghost","current_task":"task-main-2","tasks":["task-main-2"],"status":"missing"}
]}
JSON

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    export VIBE_ROOT="'"$VIBE_ROOT"'"
    export VIBE_LIB="'"$VIBE_ROOT"'/lib"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 0
    }
    _flow_status --json
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ '"feature": "refactor"' ]]
  [[ "$output" =~ '"current_task": "task-main"' ]]
  [[ ! "$output" =~ '"branch": "main"' ]]
  [[ ! "$output" =~ '"feature": "ghost"' ]]
}

@test "4. _detect_feature extracts feature from dir name" {
  # Create a fake worktree dir and extract feature
  mkdir -p /tmp/wt-claude-myfeature
  cd /tmp/wt-claude-myfeature
  run zsh -c "source $VIBE_ROOT/lib/config.sh && source $VIBE_ROOT/lib/utils.sh && source $VIBE_ROOT/lib/flow.sh && _detect_feature"
  [ "$status" -eq 0 ]
  [ "$output" = "myfeature" ]
  rm -rf /tmp/wt-claude-myfeature
}

@test "5. _detect_agent extracts agent from dir name" {
  # Create a fake worktree dir and extract agent
  mkdir -p /tmp/wt-opencode-myfeature
  cd /tmp/wt-opencode-myfeature
  run zsh -c "source $VIBE_ROOT/lib/config.sh && source $VIBE_ROOT/lib/utils.sh && source $VIBE_ROOT/lib/flow.sh && _detect_agent"
  [ "$status" -eq 0 ]
  [ "$output" = "opencode" ]
  rm -rf /tmp/wt-opencode-myfeature
}

@test "6. _flow_sync returns non-zero with deprecation guidance" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_sync
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "no longer supports cross-worktree branch merges" ]]
}

# --- Multi-task worktree alignment tests ---
# Tests 7-9: flow bind (inside feature worktree wt-agent-feature)

@test "7. vibe flow bind binds task to current feature worktree" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/wt-claude-refactor"; return 0; fi
      if [[ "$1" == "config" ]]; then return 0; fi
      return 0
    }
    _flow_bind 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Binding" ]]
}

@test "8. vibe flow bind in feature worktree updates worktrees.json with tasks array" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/wt-claude-refactor"; return 0; fi
      if [[ "$1" == "config" ]]; then return 0; fi
      return 0
    }
    _flow_bind 2026-03-02-rotate-alignment
    # Verify worktrees.json has the task in tasks array
    jq -e ".worktrees[] | select(.worktree_name == \"wt-claude-refactor\") | .tasks | index(\"2026-03-02-rotate-alignment\")" "'"$fixture"'/vibe/worktrees.json" >/dev/null
  '

  [ "$status" -eq 0 ]
}

@test "8.1 vibe flow bind forwards --agent to task update" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _vibe_task_update() { echo "TASK_UPDATE:$*"; return 0; }
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/wt-claude-refactor"; return 0; fi
      return 0
    }
    _flow_bind 2026-03-02-rotate-alignment --agent codex
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "TASK_UPDATE:2026-03-02-rotate-alignment --status in_progress --bind-current --agent codex" ]]
}

@test "8.2 vibe flow bind does not invoke legacy wtinit hook" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    wtinit() { echo "WTINIT_CALLED"; return 1; }
    _vibe_task_update() { echo "TASK_UPDATE:$*"; return 0; }
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/wt-claude-refactor"; return 0; fi
      return 0
    }
    _flow_bind 2026-03-02-rotate-alignment --agent codex
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "TASK_UPDATE:2026-03-02-rotate-alignment --status in_progress --bind-current --agent codex" ]]
  [[ ! "$output" =~ "WTINIT_CALLED" ]]
}

@test "9. vibe flow bind fails when task missing" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-claude-refactor" "$fixture/wt-claude-refactor/.vibe"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "config" ]]; then return 0; fi
      return 1
    }
    _flow_bind 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Task not found" ]]
}
@test "10. _flow_done fails when worktree is dirty" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_branch_ref() { echo "feature-branch"; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    git() {
      case "$*" in
        "branch --show-current") echo "feature-branch"; return 0 ;;
        "status --porcelain") echo "M modified-file"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_is_main_worktree() { return 1; }
    _flow_done
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Working directory is not clean" ]]
}

@test "11. _flow_done fails when branch has unmerged commits" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_branch_ref() { echo "feature-branch"; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_branch_pr_merged() { return 1; }
    git() {
      case "$*" in
        "branch --show-current") echo "feature-branch"; return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "rev-list origin/main..feature-branch") echo "commit-hash"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_is_main_worktree() { return 1; }
    _flow_done
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "has commits not merged into origin/main" ]]
}

@test "11.0 _flow_done accepts squash-merged PR state even when branch ancestry diverges" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_branch_ref() { echo "feature-branch"; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_branch_pr_merged() { return 0; }
    _flow_history_close() { echo "HISTORY_CLOSED"; return 0; }
    _flow_close_branch_runtime() { echo "RUNTIME_CLOSED"; return 0; }
    vibe_delete_local_branch() { echo "DELETE_LOCAL:$1:$2"; return 0; }
    git() {
      case "$*" in
        "branch --show-current") echo "other-branch"; return 0 ;;
        "show-ref --verify --quiet refs/heads/feature-branch") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/feature-branch") return 1 ;;
        "fetch origin main --quiet") return 0 ;;
        "rev-list origin/main..feature-branch") echo "commit-hash"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_is_main_worktree() { return 1; }
    _flow_done --branch feature-branch
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "HISTORY_CLOSED" ]]
  [[ "$output" =~ "DELETE_LOCAL:feature-branch:force" ]]
}

@test "11.1 _flow_done closes flow history and deletes local and remote branches" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-claude-refactor"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[
  {"task_id":"task-main","title":"Main Task","status":"in_progress","next_step":"Gate 4","assigned_worktree":"wt-claude-refactor","agent":"claude","pr_ref":"#42","issue_refs":["#7"]}
]}
JSON
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[
  {"worktree_name":"wt-claude-refactor","worktree_path":"FIXTURE_PATH","branch":"task/feature-branch","current_task":"task-main","tasks":["task-main"],"status":"active"}
]}
JSON
  perl -0pi -e 's#FIXTURE_PATH#'"$fixture"'/wt-claude-refactor#' "$fixture/vibe/worktrees.json"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_is_main_worktree() { return 1; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_checkout_detached_main() { echo "DETACHED_MAIN"; return 0; }
    vibe_delete_local_branch() { echo "DELETE_LOCAL:$1"; return 0; }
    vibe_delete_remote_branch() { echo "DELETE_REMOTE:$1"; return 0; }
    git() {
      case "$*" in
        "branch --show-current") echo "task/feature-branch"; return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "show-ref --verify --quiet refs/heads/task/feature-branch") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/task/feature-branch") return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "rev-list origin/main..task/feature-branch") echo ""; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_done
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "DETACHED_MAIN" ]]
  [[ "$output" =~ "DELETE_LOCAL:task/feature-branch" ]]
  [[ "$output" =~ "DELETE_REMOTE:task/feature-branch" ]]
  [[ "$output" =~ "History preserved" ]]
  [ "$(jq -r '.flows[0].state' "$fixture/vibe/flow-history.json")" = "closed" ]
  [ "$(jq -r '.flows[0].feature' "$fixture/vibe/flow-history.json")" = "feature-branch" ]
  [ "$(jq -r '.worktrees[0].branch // "null"' "$fixture/vibe/worktrees.json")" = "null" ]
}

@test "11.2 _flow_done rejects unknown options" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_done --branhc feature-branch
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown option" ]]
  [[ "$output" =~ "Usage:" ]]
}

@test "11.3 _flow_done blocks main worktree even for explicit target branch" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      case "$*" in
        "branch --show-current") echo "main"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_is_main_worktree() { return 0; }
    _flow_done --branch feature-branch
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "protected" ]]
}

@test "11.4 _flow_done accepts remote branch refs" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_history_close() { echo "HISTORY:$1:$2"; return 0; }
    _flow_close_branch_runtime() { echo "RUNTIME_CLOSED:$1"; return 0; }
    vibe_delete_local_branch() { echo "DELETE_LOCAL:$1"; return 0; }
    vibe_delete_remote_branch() { echo "DELETE_REMOTE:$1"; return 0; }
    git() {
      case "$*" in
        "branch --show-current") echo "other-branch"; return 0 ;;
        "show-ref --verify --quiet refs/heads/origin/feature-branch") return 1 ;;
        "show-ref --verify --quiet refs/heads/feature-branch") return 1 ;;
        "show-ref --verify --quiet refs/remotes/origin/feature-branch") return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "rev-list origin/main..origin/feature-branch") echo ""; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_is_main_worktree() { return 1; }
    _flow_done --branch origin/feature-branch
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "HISTORY:feature-branch:feature-branch" ]]
  [[ "$output" =~ "DELETE_REMOTE:feature-branch" ]]
  [[ ! "$output" =~ "DELETE_LOCAL:feature-branch" ]]
}

@test "12. _flow_pr skips bump if PR already exists" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; } # Mock all tools as present
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;; # PR exists
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping version bump" ]]
}

@test "13. _flow_pr skips bump if changelog message exists" {
  local fixture; fixture="$(mktemp -d)"; cd "$fixture"
  echo "## [2.1.0] - 2026-03-05" > CHANGELOG.md
  echo "- test commit ..." >> CHANGELOG.md
  
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; } # Mock all tools as present
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;; # PR does not exist
        "pr create --title test --body test --base main --web") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test" --msg "test commit ..."
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping version bump" ]]
}

@test "14. _flow_pr runs bump when no existing PR and changelog has no message" {
  local fixture; fixture="$(mktemp -d)"; cd "$fixture"
  mkdir -p scripts
  cat > scripts/bump.sh <<'EOF'
#!/usr/bin/env bash
touch bump_called
exit 0
EOF
  chmod +x scripts/bump.sh
  echo "2.1.4" > VERSION
  echo "# Changelog" > CHANGELOG.md

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;;
        "pr create --title test --body test --base main --web") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "add VERSION CHANGELOG.md") return 0 ;;
        "commit -m chore: bump version to 2.1.4") return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test" --msg "fresh release note"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Bumping version" ]]
  [ -f "$fixture/bump_called" ]
}

@test "14.1 _flow_pr allows inferred main as default base" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "main"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base main --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "log origin/main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping version bump" ]]
}

@test "14.2 _flow_pr refuses non-main inferred base without explicit override" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_pick_pr_base() { echo "claude/refactor"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base claude/refactor --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "log main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "log claude/refactor..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --title "test" --body "test"
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "claude/refactor" ]]
  [[ "$output" =~ "--base" ]]
}

@test "14.3 _flow_pr keeps GitHub base name separate from git history ref" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "develop"; return 0; }
    _flow_pr_base_git_ref() { echo "origin/develop"; return 0; }
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base develop --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;;
        "pr edit current-branch --base develop --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "log origin/develop..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --base develop --title "test" --body "test"
  '
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Using PR base: develop" ]]
}

@test "14.4 _flow_pr_base_git_ref prefers origin base over stale local branch" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      case "$*" in
        "fetch origin main --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/main") return 0 ;;
        "show-ref --verify --quiet refs/heads/main") return 0 ;;
        *) return 1 ;;
      esac
    }
    _flow_pr_base_git_ref main
  '

  [ "$status" -eq 0 ]
  [ "$output" = "origin/main" ]
}

@test "14.5 _flow_pr rejects local-only PR base when gh is used" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_resolve_pr_base() { echo "develop"; return 0; }
    vibe_has() { return 0; }
    gh() { return 0; }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "fetch origin develop --quiet") return 0 ;;
        "show-ref --verify --quiet refs/remotes/origin/develop") return 1 ;;
        "show-ref --verify --quiet refs/heads/develop") return 0 ;;
        "ls-remote --exit-code --heads origin develop") return 1 ;;
        *) return 0 ;;
      esac
    }
    _flow_pr --base develop --title "test" --body "test"
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "origin/develop not found" ]]
}



@test "14. vibe flow start with path feature does not auto-create or bind task" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/repo"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    cd "'"$fixture"'/repo"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"

    _vibe_task_add() { echo "CALLED" > "'"$fixture"'/task_add_called"; return 0; }
    _vibe_task_update() { echo "CALLED" > "'"$fixture"'/task_update_called"; return 0; }
    wtnew() {
      echo "$1" > "'"$fixture"'/wtnew_branch"
      mkdir -p "'"$fixture"'/wt-$1"
      return 0
    }

    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/repo"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 0
    }

    _flow_start_worktree "docs/plans/2026-03-02-vibe-new-task-flow-convergence.md" "claude" "main"
  '

  [ "$status" -eq 0 ]
  [ ! -f "$fixture/task_add_called" ]
  [ ! -f "$fixture/task_update_called" ]
  [ "$(cat "$fixture/wtnew_branch")" = "2026-03-02-vibe-new-task-flow-convergence" ]
  [[ "$output" =~ "cd " ]]
  [[ "$output" =~ "vibe task add" ]]
  [[ "$output" =~ "vibe flow bind" ]]
}

@test "14.3 vibe flow help no longer lists switch as a primary command" {
  run vibe flow help

  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "switch" ]]
}

@test "15. vibe flow start fails cleanly when worktree creation fails" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/repo"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    cd "'"$fixture"'/repo"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"

    wtnew() { return 1; }

    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/repo"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "branch" ]]; then return 1; fi
      return 0
    }

    _flow_start_worktree "docs/plans/2026-03-02-vibe-new-task-flow-convergence.md" "claude" "main"
  '

  [ "$status" -eq 1 ]
  [ "$(jq '.tasks | length' "$fixture/vibe/registry.json")" -eq 0 ]
}

@test "16. vibe flow start rolls back worktree when entering worktree fails" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/repo"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"
  printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$fixture/vibe/worktrees.json"

  run zsh -c '
    cd "'"$fixture"'/repo"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"

    wtnew() { return 0; }

    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/repo"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "branch" ]]; then return 1; fi
      if [[ "$1" == "worktree" && "$2" == "remove" ]]; then return 0; fi
      return 0
    }

    _flow_start_worktree "docs/plans/2026-03-02-vibe-new-task-flow-convergence.md" "claude" "main"
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Failed to enter worktree" ]]
  [ "$(jq '.tasks | length' "$fixture/vibe/registry.json")" -eq 0 ]
}


@test "17. vibe flow list rejects unsupported --keywords option" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_list --keywords Roadmap
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown option for flow list" ]]
}

@test "18. vnew forwards base arg and opens branch workspace" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/alias/worktree.sh"
    vibe_die() { echo "ERR:$*"; return 1; }
    wtnew() { echo "WTNEW:$*"; return 0; }
    vup() { echo "VUP:$*"; return 0; }
    CYAN=""
    NC=""
    vnew feat-x develop
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "WTNEW:feat-x develop" ]]
  [[ "$output" =~ "VUP:feat-x" ]]
}
