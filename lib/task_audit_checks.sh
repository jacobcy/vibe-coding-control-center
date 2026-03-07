#!/usr/bin/env zsh
# lib/task_audit_checks.sh - Registration/OpenSpec/plans checks

_task_extract_branch_pattern() {
  local branch_name="$1"
  local normalized_branch="${branch_name#refs/heads/}"
  local pattern=""

  if [[ "$normalized_branch" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)$ ]]; then
    pattern="${match[1]}"
  elif [[ "$normalized_branch" =~ ^[^/]+/([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)$ ]]; then
    pattern="${match[1]}"
  fi

  [[ -n "$pattern" ]] || return 1
  echo "$pattern"
}

_task_is_branch_registered() {
  local branch_pattern="$1"
  local registry_file="$2"

  jq -e --arg pattern "$branch_pattern" \
    '.tasks[]? | select(.task_id == $pattern or .slug == $pattern)' \
    "$registry_file" >/dev/null 2>&1
}

_task_check_branch_registration() {
  local common_dir="$1"
  local worktrees_file="$common_dir/vibe/worktrees.json"
  local registry_file="$common_dir/vibe/registry.json"
  local -a unregistered_branches
  local line wt_name branch pattern

  while IFS= read -r line; do
    wt_name=$(echo "$line" | cut -d'|' -f1)
    branch=$(echo "$line" | cut -d'|' -f2)
    pattern=$(_task_extract_branch_pattern "$branch")

    if [[ -n "$pattern" ]] && ! _task_is_branch_registered "$pattern" "$registry_file"; then
      unregistered_branches+=("$wt_name|$branch|$pattern")
    fi
  done < <(jq -r '.worktrees[]? | select(.branch != null and .branch != "") | "\(.worktree_name)|\(.branch)"' "$worktrees_file" 2>/dev/null)

  [[ ${#unregistered_branches[@]} -eq 0 ]] && return 0

  for line in "${unregistered_branches[@]}"; do
    echo "$line"
  done

  return ${#unregistered_branches[@]}
}

_task_check_openspec_sync() {
  local common_dir="$1"
  local registry_file="$common_dir/vibe/registry.json"
  local repo_root="${common_dir%/.git}"
  local openspec_changes_dir="$repo_root/openspec/changes"
  local -a unsynced_changes

  [[ -d "$openspec_changes_dir" ]] || return 0

  local bridge_script="$VIBE_ROOT/scripts/openspec_bridge.sh"
  local bridge_enabled=0
  [[ -f "$bridge_script" ]] && bridge_enabled=1

  local change_dir change_name in_registry tasks_file has_tasks_file total_tasks done_tasks
  local bridge_task expected_task_id expected_source_path
  while IFS= read -r change_dir; do
    change_name=$(basename "$change_dir")
    [[ "$change_name" == "archive" ]] && continue

    expected_task_id="$change_name"
    expected_source_path="openspec/changes/$change_name"
    bridge_task=""
    if [[ "$bridge_enabled" -eq 1 ]]; then
      bridge_task=$(cd "$repo_root" && zsh "$bridge_script" find "$change_name" 2>/dev/null || true)
      if [[ -n "$bridge_task" ]] && echo "$bridge_task" | jq -e . >/dev/null 2>&1; then
        expected_task_id=$(echo "$bridge_task" | jq -r '.task_id // empty')
        expected_source_path=$(echo "$bridge_task" | jq -r '.source_path // empty')
        [[ -z "$expected_task_id" ]] && expected_task_id="$change_name"
        [[ -z "$expected_source_path" ]] && expected_source_path="openspec/changes/$change_name"
      else
        expected_task_id="$change_name"
        expected_source_path="openspec/changes/$change_name"
      fi
    fi

    in_registry="false"
    if jq -e --arg change "$change_name" --arg tid "$expected_task_id" --arg source "$expected_source_path" \
      '.tasks[]? | select(
        .task_id == $tid or
        .task_id == $change or
        .slug == $change or
        (.openspec_change // "") == $change or
        (.source_path // "") == $source
      )' \
      "$registry_file" >/dev/null 2>&1; then
      in_registry="true"
    fi

    tasks_file="$change_dir/tasks.md"
    has_tasks_file="false"
    total_tasks=0
    done_tasks=0

    if [[ -f "$tasks_file" ]]; then
      has_tasks_file="true"
      total_tasks=$(grep -E '^- \[( |x|X)\]' "$tasks_file" 2>/dev/null | wc -l | tr -d ' ')
      done_tasks=$(grep -E '^- \[[xX]\]' "$tasks_file" 2>/dev/null | wc -l | tr -d ' ')
    fi

    echo "$change_name|$has_tasks_file|$total_tasks|$done_tasks|$in_registry"
    [[ "$in_registry" == "false" ]] && unsynced_changes+=("$change_name")
  done < <(find "$openspec_changes_dir" -maxdepth 1 -type d ! -path "$openspec_changes_dir")

  return ${#unsynced_changes[@]}
}

_task_check_plans_prds() {
  local common_dir="$1"
  local registry_file="$common_dir/vibe/registry.json"
  local repo_root="${common_dir%/.git}"
  local plans_dir="$repo_root/docs/plans"
  local prds_dir="$repo_root/docs/prds"
  local -a untracked_files
  local file file_name

  if [[ -d "$plans_dir" ]]; then
    while IFS= read -r file; do
      file_name=$(basename "$file" .md)
      if ! jq -e --arg name "$file_name" \
        '.tasks[]? | select(.task_id == $name or .slug == $name or ((.source_path // "") | test($name)))' \
        "$registry_file" >/dev/null 2>&1; then
        untracked_files+=("plans|${file#$repo_root/}")
      fi
    done < <(find "$plans_dir" -name "*.md" -type f 2>/dev/null)
  fi

  if [[ -d "$prds_dir" ]]; then
    while IFS= read -r file; do
      file_name=$(basename "$file" .md)
      if ! jq -e --arg name "$file_name" \
        '.tasks[]? | select(.task_id == $name or .slug == $name or ((.source_path // "") | test($name)))' \
        "$registry_file" >/dev/null 2>&1; then
        untracked_files+=("prds|${file#$repo_root/}")
      fi
    done < <(find "$prds_dir" -name "*.md" -type f 2>/dev/null)
  fi

  [[ ${#untracked_files[@]} -eq 0 ]] && return 0

  for file in "${untracked_files[@]}"; do
    echo "$file"
  done

  return ${#untracked_files[@]}
}
