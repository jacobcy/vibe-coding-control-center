#!/usr/bin/env bats

setup() {
  export PATH="$BATS_TEST_DIRNAME/../bin:$PATH"
  export VIBE_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  export VIBE_LIB="$VIBE_ROOT/lib"
}

@test "1. bin/vibe is executable" {
  [ -x "$BATS_TEST_DIRNAME/../bin/vibe" ]
}

@test "2. bin/vibe check --help returns success" {
  run vibe check --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
  [[ "$output" =~ "roadmap" ]]
  [[ "$output" =~ "task" ]]
  [[ "$output" =~ "flow" ]]
  [[ "$output" =~ "bootstrap" ]]
  [[ "$output" =~ "link" ]]
  [[ "$output" =~ "json <file>" ]]
  [[ "$output" =~ "docs" ]]
}

@test "2.1 vibe check check --json returns grouped result" {
  run vibe check check --json
  [[ "$status" -eq 0 || "$status" -eq 1 ]]
  echo "$output" | jq -e '.roadmap and .task and .flow and .bootstrap and .link and .docs' >/dev/null
}

@test "2.2 vibe check roadmap --json warns on unlinked roadmap items" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Ship roadmap links",
  "items": [
    {
      "roadmap_item_id": "rm-1",
      "title": "Alpha",
      "description": null,
      "status": "current",
      "source_type": "local",
      "source_refs": [],
      "issue_refs": [],
      "linked_task_ids": [],
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00"
    }
  ]
}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/roadmap.sh"
    source "'"$VIBE_ROOT"'/lib/check.sh"
    vibe() {
      local cmd="$1"
      shift
      case "$cmd" in
        roadmap) vibe_roadmap "$@" ;;
        check) vibe_check "$@" ;;
        *) return 1 ;;
      esac
    }
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_check roadmap --json
  '

  [ "$status" -eq 0 ]
  [ "$(echo "$output" | jq -r '.roadmap.status')" = "pass" ]
  [ "$(echo "$output" | jq -r '.roadmap.warnings[0]')" = "unlinked roadmap item: rm-1" ]
}

@test "2.3 vibe check link --json fails on missing roadmap back-link" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{
  "schema_version": "v2",
  "tasks": [
    {
      "task_id": "task-1",
      "title": "Task One",
      "description": null,
      "status": "todo",
      "source_type": "local",
      "source_refs": [],
      "roadmap_item_ids": ["rm-1"],
      "issue_refs": [],
      "pr_ref": null,
      "related_task_ids": [],
      "current_subtask_id": null,
      "subtasks": [],
      "runtime_worktree_name": null,
      "runtime_worktree_path": null,
      "runtime_branch": null,
      "runtime_agent": null,
      "next_step": null,
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00",
      "completed_at": null,
      "archived_at": null
    }
  ]
}
JSON
  cat > "$fixture/vibe/roadmap.json" <<'JSON'
{
  "schema_version": "v2",
  "version_goal": "Ship roadmap links",
  "items": [
    {
      "roadmap_item_id": "rm-1",
      "title": "Alpha",
      "description": null,
      "status": "current",
      "source_type": "local",
      "source_refs": [],
      "issue_refs": [],
      "linked_task_ids": [],
      "created_at": "2026-03-08T10:00:00+08:00",
      "updated_at": "2026-03-08T10:00:00+08:00"
    }
  ]
}
JSON
  cat > "$fixture/vibe/worktrees.json" <<'JSON'
{"schema_version":"v1","worktrees":[]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/check.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_check link --json
  '

  [ "$status" -eq 1 ]
  [ "$(echo "$output" | jq -r '.link.status')" = "fail" ]
  [ "$(echo "$output" | jq -r '.link.errors[0]')" = "roadmap item missing task back-link: rm-1:task-1" ]
}

@test "2.4 vibe task audit --all does not fail-fast when worktrees.json is missing" {
  local fixture
  fixture="$(mktemp -d)"
  mkdir -p "$fixture/vibe"
  cat > "$fixture/vibe/registry.json" <<'JSON'
{"schema_version":"v1","tasks":[]}
JSON

  run zsh -c '
    source "'"$VIBE_ROOT"'/lib/config.sh"
    source "'"$VIBE_ROOT"'/lib/utils.sh"
    source "'"$VIBE_ROOT"'/lib/task.sh"
    git() {
      case "$*" in
        "rev-parse --is-inside-work-tree") return 0 ;;
        "rev-parse --git-common-dir") echo "'"$fixture"'"; return 0 ;;
        "rev-parse --show-toplevel") echo "'"$fixture"'"; return 0 ;;
        *) command git "$@" ;;
      esac
    }
    vibe_task audit --all
  '

  [ "$status" -eq 0 ]
  [[ "$output" =~ "Audit Summary Report" ]]
}

@test "3. vibe help outputs Usage" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "4. vibe without args returns help info" {
  run vibe
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
}

@test "4.1 vibe help mentions issue to task to flow onboarding" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "repo issue / roadmap item" ]]
}

@test "4.2 vibe help mentions task command" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "execution record 生命周期管理" ]]
}

@test "4.4 vibe help mentions task add update remove" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "list, add, update, remove" ]]
}

@test "4.5 vibe alias load points to the new runtime loader" {
  run vibe alias --load
  [ "$status" -eq 0 ]
  [[ -f "$output" ]]
  [[ "$output" =~ "alias/loader.sh" ]]
  [[ ! "$output" =~ "config/aliases.sh" ]]
}

@test "4.3 vibe help does not advertise unsupported skills audit subcommand" {
  run vibe help
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "sync, check, audit" ]]
}

@test "5. invalid subcommand returns error" {
  run vibe invalidcommand
  [ "$status" -eq 1 ]
  [[ "$output" =~ "Unknown command" ]]
}

@test "6. VIBE_ROOT is set correctly in script" {
  local expected_root
  expected_root="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  run zsh -c "unset VIBE_ROOT VIBE_LIB; source $BATS_TEST_DIRNAME/../bin/vibe >/dev/null && echo \$VIBE_ROOT"
  [ "$status" -eq 0 ]
  [ "$output" = "$expected_root" ]
}

@test "7. vibe version outputs version info" {
  run vibe version
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe" ]]
}

@test "8. vibe task help lists subcommands" {
  run vibe task --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Usage:" ]]
  [[ "$output" =~ "vibe task" ]]
  [[ "$output" =~ "add" ]]
  [[ "$output" =~ "show" ]]
  [[ "$output" =~ "update" ]]
  [[ "$output" =~ "remove" ]]
  [[ "$output" =~ "audit" ]]
  [[ ! "$output" =~ "sync" ]]
}

@test "9. vibe flow bind help mentions task id" {
  run vibe flow bind --help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "vibe flow bind <task-id>" ]]
}

@test "10. vibe roadmap help is available" {
  run vibe roadmap help
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Vibe Roadmap" ]]
  [[ "$output" =~ "classify" ]]
}

@test "11. global vibe delegates to repo bin/vibe inside a git repo" {
  local fixture home_dir global_root
  fixture="$(mktemp -d)"
  home_dir="$(mktemp -d)"
  global_root="$home_dir/.vibe"
  git -C "$fixture" init >/dev/null 2>&1
  mkdir -p "$fixture/bin" "$global_root/bin"
  cp "$BATS_TEST_DIRNAME/../bin/vibe" "$global_root/bin/vibe"
  chmod +x "$global_root/bin/vibe"
  cat > "$fixture/bin/vibe" <<'SH'
#!/usr/bin/env zsh
echo "LOCAL-REPO-VIBE"
SH
  chmod +x "$fixture/bin/vibe"

  run env HOME="$home_dir" zsh -c 'cd "'"$fixture"'" && "'"$global_root"'/bin/vibe" version'
  [ "$status" -eq 0 ]
  [ "$output" = "LOCAL-REPO-VIBE" ]
}

@test "12. config aliases shim supports installed aliases directory without alias loader" {
  local fixture home_dir config_dir aliases_dir
  fixture="$(mktemp -d)"
  home_dir="$fixture/home"
  config_dir="$home_dir/.vibe/config"
  aliases_dir="$config_dir/aliases"

  mkdir -p "$aliases_dir"
  cp "$BATS_TEST_DIRNAME/../config/aliases.sh" "$config_dir/aliases.sh"
  cp "$BATS_TEST_DIRNAME/../alias/git.sh" "$aliases_dir/git.sh"
  cp "$BATS_TEST_DIRNAME/../alias/vibe.sh" "$aliases_dir/vibe.sh"

  run env HOME="$home_dir" zsh -c 'source "'"$config_dir"'/aliases.sh"'
  [ "$status" -eq 0 ]
  [[ ! "$output" =~ "alias/loader.sh not found" ]]
}
