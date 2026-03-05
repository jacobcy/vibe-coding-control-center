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
  [[ "$output" =~ "sync" ]]
  [[ "$output" =~ "review" ]]
  [[ "$output" =~ "pr" ]]
}

@test "2. vibe flow new without args returns error" {
  run vibe flow new
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Usage: vibe flow new" ]]
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

@test "12. _flow_pr skips bump if PR already exists" {
  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    vibe_has() { return 0; } # Mock all tools as present
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 0 ;; # PR exists
        "pr edit current-branch --title test --body test") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "log main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        "config --get user.name") echo "test"; return 0 ;;
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
    vibe_has() { return 0; } # Mock all tools as present
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;; # PR does not exist
        "pr create --title test --body test --web") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "log main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
        "push origin HEAD") return 0 ;;
        "config --get user.name") echo "test"; return 0 ;;
        *) return 0 ;;
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
    vibe_has() { return 0; }
    gh() {
      case "$*" in
        "pr list --state open --base main --json number,headRefName,title") echo "[]"; return 0 ;;
        "pr view current-branch") return 1 ;;
        "pr create --title test --body test --web") return 0 ;;
        *) return 0 ;;
      esac
    }
    git() {
      case "$*" in
        "branch --show-current") echo "current-branch"; return 0 ;;
        "log main..HEAD --oneline") echo "abcdef test commit"; return 0 ;;
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

@test "15. _flow_bind normalizes identity even when wtinit exists" {
  local fixture
  fixture="$(mktemp -d)"
  make_flow_task_fixture "$fixture"
  local calls="$fixture/git_config_calls.log"
  : > "$calls"

  run zsh -c '
    cd "'"$fixture"'/wt-claude-refactor"
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/flow.sh"
    wtinit() { return 0; }
    git() {
      if [[ "$1" == "rev-parse" && "$2" == "--git-common-dir" ]]; then echo "'"$fixture"'"; return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--is-inside-work-tree" ]]; then return 0; fi
      if [[ "$1" == "rev-parse" && "$2" == "--show-toplevel" ]]; then echo "'"$fixture"'/wt-claude-refactor"; return 0; fi
      if [[ "$1" == "config" ]]; then echo "$*" >> "'"$calls"'"; return 0; fi
      return 0
    }
    _flow_bind 2026-03-02-rotate-alignment --agent claude
  '

  [ "$status" -eq 0 ]
  grep -q "config user.name claude" "$calls"
  grep -q "config user.email claude@vibe.coding" "$calls"
}

@test "14. vibe flow start with path feature uses sanitized branch and prints cd next-step" {
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

    _vibe_task_today() { echo "2026-03-05"; }
    _vibe_task_add() { echo "$*" > "'"$fixture"'/task_add_args"; return 0; }
    _vibe_task_update() { return 0; }
    wtnew() {
      echo "$1" > "'"$fixture"'/wtnew_branch"
      mkdir -p "'"$fixture"'/wt-claude-$1"
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
  [[ "$(cat "$fixture/task_add_args")" =~ "--id 2026-03-05-2026-03-02-vibe-new-task-flow-convergence" ]]
  [ "$(cat "$fixture/wtnew_branch")" = "2026-03-02-vibe-new-task-flow-convergence" ]
  [[ "$output" =~ "cd " ]]
  [[ "$output" =~ "vup" ]]
}

@test "15. vibe flow start rolls back task when worktree creation fails" {
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

    _vibe_task_today() { echo "2026-03-05"; }
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

@test "16. vibe flow start rolls back task when entering worktree fails" {
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

    _vibe_task_today() { echo "2026-03-05"; }
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
