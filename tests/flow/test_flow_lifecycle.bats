#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/flow_common.bash"

@test "2. vibe flow new without args returns error" {
  run vibe flow new
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Usage: vibe flow new" ]]
}

@test "2.2 vibe flow switch without args returns error" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_switch
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Usage: vibe flow switch" ]]
}

@test "2.3 _flow_new refuses dirty worktree without --save-unstash" {
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

@test "2.4 _flow_new refuses protected main branch rotation" {
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
        *) return 0 ;;
      esac
    }

    _flow_new next-flow
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "protected" || "$output" =~ "main" ]]
}

@test "2.5 _flow_new stashes changes and creates a new branch when requested" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }

    last_stash_oid="oid-new"

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo "M dirty-file"; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "stash push -u -m "*) echo "STASHED"; return 0 ;;
        "rev-parse -q --verify refs/stash") echo "$last_stash_oid"; return 0 ;;
        "stash list --format=%H %gd") echo "$last_stash_oid stash@{0}"; return 0 ;;
        "checkout -b task/next-flow main") echo "CHECKOUT_NEW"; return 0 ;;
        "stash apply stash@{0}") echo "APPLIED"; return 0 ;;
        "stash drop stash@{0}") echo "DROPPED"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow --branch main --save-unstash
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CHECKOUT_NEW" ]]
  [[ "$output" =~ "APPLIED" ]]
  [[ "$output" =~ "DROPPED" ]]
}

@test "2.5.0 _flow_new defaults to origin/main when branch is omitted" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }
    _flow_update_current_worktree_branch() { return 0; }

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "checkout -b task/next-flow origin/main") echo "CHECKOUT_DEFAULT"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CHECKOUT_DEFAULT" ]]
}

@test "2.5.0a _flow_new allows detached HEAD and creates a new branch from origin/main" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }
    _flow_update_current_worktree_branch() { return 0; }

    git() {
      case "$*" in
        "branch --show-current") echo ""; return 0 ;;
        "status --porcelain") echo ""; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "checkout -b task/next-flow origin/main") echo "CHECKOUT_FROM_DETACHED"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CHECKOUT_FROM_DETACHED" ]]
}

@test "2.5.1 _flow_new restores the original branch when runtime update fails" {
  local branch_cleanup_marker
  branch_cleanup_marker="$(mktemp)"
  rm -f "$branch_cleanup_marker"

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 1; }
    _flow_update_current_worktree_branch() { return 1; }

    last_stash_oid="oid-new"

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo "M dirty-file"; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "stash push -u -m "*) return 0 ;;
        "rev-parse -q --verify refs/stash") echo "$last_stash_oid"; return 0 ;;
        "stash list --format=%H %gd") echo "$last_stash_oid stash@{0}"; return 0 ;;
        "checkout -b task/next-flow main") echo "CHECKOUT_NEW"; return 0 ;;
        "checkout task/existing-flow") echo "CHECKOUT_ORIGINAL"; return 0 ;;
        "branch -D task/next-flow") : > "'"$branch_cleanup_marker"'"; return 0 ;;
        "stash apply stash@{0}") echo "RESTORED"; return 0 ;;
        "stash drop stash@{0}") echo "DROPPED"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_new next-flow --branch main --save-unstash
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "CHECKOUT_NEW" ]]
  [[ "$output" =~ "CHECKOUT_ORIGINAL" ]]
  [ -f "$branch_cleanup_marker" ]
  [[ "$output" =~ "RESTORED" ]]
  [[ "$output" =~ "DROPPED" ]]
  [[ "$output" =~ "Failed to update worktree runtime state" ]]
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

    last_stash_message=""

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo "M dirty-file"; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "stash push -u -m "*) last_stash_message="${@: -1}"; echo "STASHED"; return 0 ;;
        "rev-parse -q --verify refs/stash") echo "oid-next"; return 0 ;;
        "stash list --format=%H %gd")
          echo "older-oid stash@{0}"
          echo "oid-next stash@{1}"
          return 0 ;;
        "checkout -b task/next-flow origin/task/next-flow") echo "CHECKOUT_EXISTING"; return 0 ;;
        "stash apply stash@{1}") echo "APPLIED"; return 0 ;;
        "stash drop stash@{1}") echo "DROPPED"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_switch next-flow
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CHECKOUT_EXISTING" ]]
  [[ "$output" =~ "RUNTIME_UPDATED" ]]
  [[ "$output" =~ "APPLIED" ]]
  [[ "$output" =~ "DROPPED" ]]
}

@test "2.6.1 _flow_switch skips stash work when the worktree is already clean" {
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
        "check-ref-format --branch task/next-flow") return 0 ;;
        "stash push -u -m "*) echo "UNEXPECTED_STASH"; return 0 ;;
        "checkout -b task/next-flow origin/task/next-flow") echo "CHECKOUT_EXISTING"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_switch next-flow
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "CHECKOUT_EXISTING" ]]
  [[ "$output" =~ "RUNTIME_UPDATED" ]]
  [[ ! "$output" =~ "UNEXPECTED_STASH" ]]
}

@test "2.6.2 _flow_switch restores the original branch when runtime update fails" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 0; }
    _flow_branch_has_pr() { return 1; }
    _flow_branch_ref() { echo "origin/task/next-flow"; return 0; }
    _flow_update_current_worktree_branch() { return 1; }

    last_stash_message=""

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo "M dirty-file"; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "stash push -u -m "*) last_stash_message="${@: -1}"; echo "STASHED"; return 0 ;;
        "rev-parse -q --verify refs/stash") echo "oid-next"; return 0 ;;
        "stash list --format=%H %gd") echo "oid-next stash@{0}"; return 0 ;;
        "checkout -b task/next-flow origin/task/next-flow") echo "CHECKOUT_NEXT"; return 0 ;;
        "checkout task/existing-flow") echo "CHECKOUT_ORIGINAL"; return 0 ;;
        "stash apply stash@{0}") echo "RESTORED"; return 0 ;;
        "stash drop stash@{0}") echo "DROPPED"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_switch next-flow
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "CHECKOUT_NEXT" ]]
  [[ "$output" =~ "CHECKOUT_ORIGINAL" ]]
  [[ "$output" =~ "RESTORED" ]]
  [[ "$output" =~ "DROPPED" ]]
  [[ "$output" =~ "Failed to update worktree runtime state" ]]
}

@test "2.6.3 _flow_switch surfaces the exact stash ref when restore conflicts" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_history_has_closed_feature() { return 1; }
    _flow_branch_exists() { return 0; }
    _flow_branch_has_pr() { return 1; }
    _flow_branch_ref() { echo "origin/task/next-flow"; return 0; }
    _flow_update_current_worktree_branch() { echo "RUNTIME_UPDATED"; return 0; }

    last_stash_message=""

    git() {
      case "$*" in
        "branch --show-current") echo "task/existing-flow"; return 0 ;;
        "status --porcelain") echo "M dirty-file"; return 0 ;;
        "check-ref-format --branch task/next-flow") return 0 ;;
        "stash push -u -m "*) last_stash_message="${@: -1}"; return 0 ;;
        "rev-parse -q --verify refs/stash") echo "oid-next"; return 0 ;;
        "stash list --format=%H %gd") echo "oid-next stash@{0}"; return 0 ;;
        "checkout -b task/next-flow origin/task/next-flow") echo "CHECKOUT_EXISTING"; return 0 ;;
        "stash apply stash@{0}") echo "APPLY_CONFLICT"; return 1 ;;
        "stash drop stash@{0}") echo "UNEXPECTED_DROP"; return 0 ;;
        *) return 0 ;;
      esac
    }

    _flow_switch next-flow
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "CHECKOUT_EXISTING" ]]
  [[ "$output" =~ "APPLY_CONFLICT" ]]
  [[ "$output" =~ "stash@{0}" ]]
  [[ "$output" =~ "Resolve manually with: git stash apply stash@{0}" ]]
  [[ ! "$output" =~ "UNEXPECTED_DROP" ]]
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
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/wt-codex-runtime-upsert"; return 0; fi
      return 0
    }
    _flow_update_current_worktree_branch "task/runtime-upsert"
    jq -r ".worktrees[0].worktree_name + \"|\" + .worktrees[0].worktree_path + \"|\" + .worktrees[0].branch + \"|\" + .worktrees[0].status" "'"$fixture"'/vibe/worktrees.json"
  '

  [ "$status" -eq 0 ]
  [ "$output" = "wt-codex-runtime-upsert|$fixture/wt-codex-runtime-upsert|task/runtime-upsert|active" ]
}

@test "2.7.1 _flow_update_current_worktree_branch resolves nested directories to the worktree root" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-codex-runtime-root/subdir"
  cat > "$fixture/vibe/worktrees.json" <<JSON
{"schema_version":"v1","worktrees":[{"worktree_name":"wt-codex-runtime-root","worktree_path":"$fixture/wt-codex-runtime-root","branch":"task/existing","current_task":"task-main","tasks":["task-main"],"status":"active"}]}
JSON

  run zsh -c '
    cd "'"$fixture"'/wt-codex-runtime-root/subdir"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/wt-codex-runtime-root"; return 0; fi
      return 0
    }
    _flow_update_current_worktree_branch "task/runtime-root"
    jq -r ".worktrees[0].worktree_name + \"|\" + .worktrees[0].worktree_path + \"|\" + .worktrees[0].branch + \"|\" + (.worktrees | length | tostring)" "'"$fixture"'/vibe/worktrees.json"
  '

  [ "$status" -eq 0 ]
  [ "$output" = "wt-codex-runtime-root|$fixture/wt-codex-runtime-root|task/runtime-root|1" ]
}

@test "2.1 _flow_new rejects legacy --base alias to keep branch semantics explicit" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    _flow_new demo --base develop
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown option: --base" ]]
  [[ "$output" =~ "--branch" ]]
}

@test "2.8 vibe flow new help no longer describes worktree creation" {
  run vibe flow new --help

  [ "$status" -eq 0 ]
  [[ "$output" =~ "save-unstash" ]]
  [[ "$output" =~ "origin/main" ]]
  [[ "$output" =~ "does not create a physical worktree" ]]
  [[ ! "$output" =~ "create a new worktree" ]]
}

@test "2.8.1 vibe flow switch help describes default safe carry semantics" {
  run vibe flow switch --help

  [ "$status" -eq 0 ]
  [[ "$output" =~ "自动" || "$output" =~ "默认" ]]
  [[ "$output" =~ "未提交改动" ]]
  [[ ! "$output" =~ "save-stash" ]]
}

@test "14. flow module no longer exposes legacy worktree-start helpers" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"

    typeset -f _flow_new_worktree >/dev/null 2>&1
    status_new=$?
    typeset -f _flow_start_worktree >/dev/null 2>&1
    status_start=$?
    echo "${status_new}|${status_start}"
  '

  [ "$status" -eq 0 ]
  [ "$output" = "1|1" ]
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
