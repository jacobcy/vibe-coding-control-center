#!/usr/bin/env bats

source "$BATS_TEST_DIRNAME/../helpers/flow_common.bash"

@test "1. vibe flow help outputs subcommands" {
  run vibe flow help
  [ "$status" -eq 0 ]
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
  [[ "$output" =~ "switch" ]]
  [[ "$output" =~ "save-unstash" ]]
}

@test "3. vibe flow status in non-worktree returns error" {
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
  mkdir -p /tmp/wt-claude-myfeature
  cd /tmp/wt-claude-myfeature
  run zsh -c "source $VIBE_ROOT/lib/config.sh && source $VIBE_ROOT/lib/utils.sh && source $VIBE_ROOT/lib/flow.sh && _detect_feature"
  [ "$status" -eq 0 ]
  [ "$output" = "myfeature" ]
  rm -rf /tmp/wt-claude-myfeature
}

@test "5. _detect_agent extracts agent from dir name" {
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