#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../bin:$PATH"
  export VIBE_ROOT="$BATS_TEST_DIRNAME/.."
  # Source needed libraries for unit tests
  source "$VIBE_ROOT/lib/config.sh"
  source "$VIBE_ROOT/lib/utils.sh"
  source "$VIBE_ROOT/lib/flow.sh"
}

make_flow_task_fixture() {
  local fixture="$1"
  local worktree_dir="${2:-$fixture/wt-claude-refactor}"

  mkdir -p "$fixture/vibe" "$worktree_dir"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[{"task_id":"2026-03-02-rotate-alignment","title":"Rotate Workflow Refinement","status":"planning","next_step":"Implement flow start."}]}
JSON
}

@test "1. vibe flow help outputs subcommands" {
  run vibe flow help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage: vibe flow <command>" ]]
  [[ "$output" =~ "start" ]]
  [[ "$output" =~ "review" ]]
  [[ "$output" =~ "pr" ]]
  [[ "$output" =~ "done" ]]
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

@test "7. vibe flow start --task reads task metadata in current directory mode" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
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

@test "8. vibe flow start --task accepts explicit agent for branch naming" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
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

@test "9. vibe flow start --task fails when task is missing" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe" "$fixture/wt-claude-refactor"
  printf '%s\n' '{"schema_version":"v1","tasks":[]}' > "$fixture/vibe/registry.json"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "Task not found" ]]
}

@test "10. vibe flow start --task rejects dirty worktree" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    git() {
      if [[ "$1" == "status" && "$2" == "--porcelain" ]]; then echo " M lib/flow.sh"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      return 1
    }
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 1 ]
  [[ "$output" =~ "dirty worktree" ]]
}

@test "11. vibe flow start --task defaults agent from current worktree context" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture" "$fixture/wt-opencode-refactor"

  run zsh -c '
    cd "'"$fixture"'/wt-opencode-refactor"
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
    _flow_start --task 2026-03-02-rotate-alignment
  '

  [ "$status" -eq 0 ]
  [ "$(cat "$fixture/branch-name")" = "opencode/2026-03-02-rotate-alignment" ]
  [ "$(cat "$fixture/git-user-name")" = "opencode" ]
}

@test "12. vibe flow start --task rejects existing target branch instead of resetting it" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
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
