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
  [[ "$output" =~ "start" ]]
  [[ "$output" =~ "done" ]]
  [[ "$output" =~ "status" ]]
  [[ "$output" =~ "sync" ]]
  [[ "$output" =~ "review" ]]
  [[ "$output" =~ "pr" ]]
}

@test "2. vibe flow start without args returns error" {
  run vibe flow start
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Usage: vibe flow start" ]]
}

@test "3. vibe flow status in non-worktree returns error" {
  # Run in a directory that is definitely not a worktree
  cd /tmp
  run vibe flow status
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Not in a worktree" ]]
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

@test "6. _flow_sync returns non-zero when any merge fails" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      case "$*" in
        "branch --show-current") echo "source-branch"; return 0 ;;
        "worktree list --porcelain")
          echo "worktree /tmp/wt-source"
          echo "worktree /tmp/wt-fail"
          return 0
          ;;
        "-C /tmp/wt-source branch --show-current") echo "source-branch"; return 0 ;;
        "-C /tmp/wt-fail branch --show-current") echo "target-branch"; return 0 ;;
        "rev-list --count target-branch..source-branch") echo "1"; return 0 ;;
        "-C /tmp/wt-fail merge source-branch --no-edit") return 1 ;;
        *) return 0 ;;
      esac
    }
    _flow_sync
  '
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Merge failed for target-branch" ]]
}

# --- Multi-task worktree alignment tests ---
# Tests 7-9: bind-to-current path (inside feature worktree wt-agent-feature)
# Tests 10-13: _flow_start_task branching path (outside feature worktree)

@test "7. vibe flow start --task binds task to current feature worktree" {
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
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Binding task" ]]
}

@test "8. vibe flow start --task in feature worktree updates worktrees.json with tasks array" {
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
    _flow_start --task 2026-03-02-rotate-alignment
    # Verify worktrees.json has the task in tasks array
    jq -e ".worktrees[] | select(.worktree_name == \"wt-claude-refactor\") | .tasks | index(\"2026-03-02-rotate-alignment\")" "'"$fixture"'/vibe/worktrees.json" >/dev/null
  '

  [ "$status" -eq 0 ]
}

@test "9. vibe flow start --task fails when task missing (feature worktree bind mode)" {
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
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Task not found" ]]
}

@test "10. vibe flow start --task in non-feature dir creates branch with correct naming" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture" "$fixture/project-root"

  run zsh -c '
    cd "'"$fixture"'/project-root"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "fetch" && "$2" == "origin" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" && "$4" == "refs/remotes/origin/main" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" ]]; then return 1; fi
      if [[ "$1" == "checkout" && "$2" == "-b" ]]; then printf "%s" "$3" > "'"$fixture"'/branch-name"; printf "%s" "$4" > "'"$fixture"'/branch-base"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.name" ]]; then return 0; fi
      if [[ "$1" == "config" && "$2" == "user.email" ]]; then return 0; fi
      return 1
    }
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ "$(cat "$fixture/branch-name")" = "claude/2026-03-02-rotate-alignment" ]
  [ "$(cat "$fixture/branch-base")" = "origin/main" ]
  [[ "$output" =~ "Rotate Workflow Refinement" ]]
}

@test "11. vibe flow start --task in non-feature dir accepts explicit agent" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture" "$fixture/project-root"

  run zsh -c '
    cd "'"$fixture"'/project-root"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "fetch" && "$2" == "origin" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" && "$4" == "refs/remotes/origin/main" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" ]]; then return 1; fi
      if [[ "$1" == "checkout" && "$2" == "-b" ]]; then printf "%s" "$3" > "'"$fixture"'/branch-name"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.name" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-name"; return 0; fi
      if [[ "$1" == "config" && "$2" == "user.email" ]]; then printf "%s" "$3" > "'"$fixture"'/git-user-email"; return 0; fi
      return 1
    }
    _flow_start --task 2026-03-02-rotate-alignment --agent codex
  '

  [ "$status" -eq 0 ]
  [ "$(cat "$fixture/branch-name")" = "codex/2026-03-02-rotate-alignment" ]
  [ "$(cat "$fixture/git-user-name")" = "codex" ]
  [ "$(cat "$fixture/git-user-email")" = "codex@vibe.coding" ]
}

@test "12. vibe flow start --task rejects existing target branch instead of resetting it" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture" "$fixture/project-root"

  run zsh -c '
    cd "'"$fixture"'/project-root"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "fetch" && "$2" == "origin" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" && "$4" == "refs/remotes/origin/main" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" && "$4" == "refs/heads/claude/2026-03-02-rotate-alignment" ]]; then return 0; fi
      if [[ "$1" == "checkout" ]]; then echo "unexpected checkout" > "'"$fixture"'/checkout-called"; return 1; fi
      return 1
    }
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "already exists" ]]
  [ ! -e "$fixture/checkout-called" ]
}

@test "13. vibe flow start --task rejects remote target branch even when local refs are stale" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture" "$fixture/project-root"

  run zsh -c '
    cd "'"$fixture"'/project-root"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "fetch" && "$2" == "origin" && "$3" == "main" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" && "$4" == "refs/remotes/origin/main" ]]; then return 0; fi
      if [[ "$1" == "show-ref" && "$2" == "--verify" ]]; then return 1; fi
      if [[ "$1" == "ls-remote" && "$2" == "--exit-code" && "$3" == "--heads" && "$4" == "origin" && "$5" == "claude/2026-03-02-rotate-alignment" ]]; then return 0; fi
      if [[ "$1" == "checkout" ]]; then echo "unexpected checkout" > "'"$fixture"'/checkout-called"; return 1; fi
      return 1
    }
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "already exists" ]]
  [ ! -e "$fixture/checkout-called" ]
}
