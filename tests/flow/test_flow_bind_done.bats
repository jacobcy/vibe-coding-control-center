#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/flow_common.bash"

# --- Multi-task worktree alignment tests ---

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
  [[ "$output" =~ "Rotate Workflow Refinement" ]]
}

@test "8. vibe flow bind in feature worktree does not mutate legacy worktrees.json state" {
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
      if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "task/feature-branch"; return 0; fi
      if [[ "$1" == "config" ]]; then return 0; fi
      return 0
    }
    _flow_bind 2026-03-02-rotate-alignment
    jq -e "(.worktrees | length) == 0" "'"$fixture"'/vibe/worktrees.json" >/dev/null
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

@test "11. _flow_done fails when reviewed branch still has unmerged commits" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_branch_ref() { echo "feature-branch"; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_branch_pr_merged() { return 1; }
    _flow_review_has_evidence() { return 0; }
    gh() { return 0; }
    vibe_has() { [[ "$1" == "gh" ]]; }
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

@test "11.0 _flow_done blocks unmerged PRs without review evidence" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_branch_ref() { echo "feature-branch"; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_branch_pr_merged() { return 1; }
    _flow_review_has_evidence() { return 1; }
    git() {
      case "$*" in
        "branch --show-current") echo "feature-branch"; return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "fetch origin main --quiet") return 0 ;;
        "rev-list origin/main..feature-branch") echo "commit-hash"; return 0 ;;
        *) return 0 ;;
      esac
    }
    _flow_is_main_worktree() { return 1; }
    _flow_done
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "review evidence" ]]
}

@test "11.1 _flow_done merges reviewed PR before closeout" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    local merged=0
    _flow_branch_ref() { echo "feature-branch"; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_branch_pr_merged() { [[ "$merged" -eq 1 ]]; }
    _flow_review_has_evidence() { return 0; }
    _flow_history_close() { echo "HISTORY_CLOSED"; return 0; }
    _flow_close_branch_runtime() { echo "RUNTIME_CLOSED"; return 0; }
    vibe_delete_local_branch() { echo "DELETE_LOCAL:$1:$2"; return 0; }
    gh() {
      case "$*" in
        "pr merge feature-branch --merge")
          merged=1
          echo "MERGED_PR"
          return 0
          ;;
        *) return 0 ;;
      esac
    }
    vibe_has() { [[ "$1" == "gh" ]]; }
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
  [[ "$output" =~ "MERGED_PR" ]]
  [[ "$output" =~ "HISTORY_CLOSED" ]]
  [[ "$output" =~ "DELETE_LOCAL:feature-branch:force" ]]
}

@test "11.2 _flow_done accepts squash-merged PR state even when branch ancestry diverges" {
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

@test "11.3 _flow_done closes flow history, lands on main branch, and deletes local and remote branches" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-claude-refactor"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[
  {"task_id":"task-main","title":"Main Task","status":"in_progress","next_step":"Gate 4","assigned_worktree":"wt-claude-refactor","runtime_worktree_name":"wt-claude-refactor","runtime_worktree_path":"FIXTURE_PATH","runtime_branch":"task/feature-branch","runtime_agent":"claude","agent":"claude","pr_ref":"#42","issue_refs":["#7"]}
]}
JSON
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[
  {"worktree_name":"wt-claude-refactor","worktree_path":"FIXTURE_PATH","branch":"task/feature-branch","current_task":"task-main","tasks":["task-main"],"status":"active"}
]}
JSON
  perl -0pi -e 's#FIXTURE_PATH#'"$fixture"'/wt-claude-refactor#' "$fixture/vibe/registry.json"
  perl -0pi -e 's#FIXTURE_PATH#'"$fixture"'/wt-claude-refactor#' "$fixture/vibe/worktrees.json"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_is_main_worktree() { return 1; }
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_has_pr() { return 0; }
    _flow_checkout_safe_main_branch() { echo "SAFE_MAIN_BRANCH"; return 0; }
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
  [[ "$output" =~ "SAFE_MAIN_BRANCH" ]]
  [[ "$output" =~ "DELETE_LOCAL:task/feature-branch" ]]
  [[ "$output" =~ "DELETE_REMOTE:task/feature-branch" ]]
  [[ "$output" =~ "task/feature-branch" ]]
  [[ "$output" =~ "History preserved" ]]
  [ "$(jq -r '.flows[0].state' "$fixture/vibe/flow-history.json")" = "closed" ]
  [ "$(jq -r '.flows[0].feature' "$fixture/vibe/flow-history.json")" = "feature-branch" ]
  [ "$(jq -r '.worktrees[0].branch // "null"' "$fixture/vibe/worktrees.json")" = "null" ]
  [ "$(jq -r '.worktrees[0].current_task // "null"' "$fixture/vibe/worktrees.json")" = "null" ]
  [ "$(jq -r '.worktrees[0].tasks | length' "$fixture/vibe/worktrees.json")" = "0" ]
  [ "$(jq -r '.tasks[0].runtime_branch // "null"' "$fixture/vibe/registry.json")" = "null" ]
  [ "$(jq -r '.tasks[0].runtime_worktree_name // "null"' "$fixture/vibe/registry.json")" = "null" ]
}

@test "11.4 _flow_done rejects unknown options" {
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

@test "11.5 _flow_done blocks main worktree even for explicit target branch" {
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

@test "11.6 _flow_done accepts remote branch refs" {
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
