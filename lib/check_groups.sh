#!/usr/bin/env zsh
# lib/check_groups.sh - Group-level checks for vibe check

_vibe_check_lines_to_json_array() {
  jq -Rsc 'split("\n") | map(select(length > 0))'
}

_vibe_check_group_json() {
  local group_status="$1" summary="$2" errors_json="$3" warnings_json="$4"
  jq -nc \
    --arg status "$group_status" \
    --arg summary "$summary" \
    --argjson errors "${errors_json:-[]}" \
    --argjson warnings "${warnings_json:-[]}" \
    '{status:$status, errors:$errors, warnings:$warnings, summary:$summary}'
}

_vibe_check_common_dir() {
  git rev-parse --git-common-dir 2>/dev/null
}

_vibe_check_group_roadmap() {
  local audit_json invalid_ids unlinked_ids errors_json warnings_json warnings group_status summary

  audit_json="$(vibe roadmap audit --check-status --check-version-goal --check-links --json 2>/dev/null)" || true
  if [[ -z "$audit_json" ]] || ! echo "$audit_json" | jq empty >/dev/null 2>&1; then
    _vibe_check_group_json "fail" "roadmap audit failed" '["vibe roadmap audit failed"]' '[]'
    return
  fi

  invalid_ids="$(echo "$audit_json" | jq -r '.checks.status.invalid_item_ids[]?')"
  unlinked_ids="$(echo "$audit_json" | jq -r '.checks.links.unlinked_item_ids[]?')"

  errors_json="$(printf '%s\n' "$invalid_ids" | sed '/^$/d' | _vibe_check_lines_to_json_array | jq 'map("invalid roadmap item status: " + .)')"

  warnings=""
  if [[ "$(echo "$audit_json" | jq -r '.checks.version_goal.present')" != "true" ]]; then
    warnings+="version_goal is empty\n"
  fi
  if [[ -n "$unlinked_ids" ]]; then
    while IFS= read -r item; do
      [[ -n "$item" ]] && warnings+="unlinked roadmap item: $item\n"
    done <<< "$unlinked_ids"
  fi
  warnings_json="$(printf '%b' "$warnings" | sed '/^$/d' | _vibe_check_lines_to_json_array)"

  if [[ "$(echo "$errors_json" | jq 'length')" -gt 0 ]]; then
    group_status="fail"
    summary="roadmap audit found invalid status entries"
  else
    group_status="pass"
    summary="roadmap audit passed"
  fi

  _vibe_check_group_json "$group_status" "$summary" "$errors_json" "$warnings_json"
}

_vibe_check_group_task() {
  local output group_status summary errors_json
  if output="$(vibe task audit --all 2>&1)"; then
    group_status="pass"
    summary="task audit passed"
    errors_json='[]'
  else
    group_status="fail"
    summary="task audit failed"
    errors_json='["vibe task audit --all failed"]'
  fi

  _vibe_check_group_json "$group_status" "$summary" "$errors_json" '[]'
}

_vibe_check_group_flow() {
  local common_dir worktrees_file invalid_status missing_paths errors warnings
  local errors_json warnings_json group_status summary

  common_dir="$(_vibe_check_common_dir)"
  [[ -n "$common_dir" ]] || { _vibe_check_group_json "fail" "not in git repo" '["Not in a git repository"]' '[]'; return; }
  worktrees_file="$common_dir/vibe/worktrees.json"
  [[ -f "$worktrees_file" ]] || { _vibe_check_group_json "fail" "missing worktrees.json" '["Missing worktrees.json"]' '[]'; return; }

  invalid_status="$(jq -r '.worktrees[]? | select((.status // "active" | IN("active","idle","missing","stale")) | not) | "\(.worktree_name):\(.status // "null")"' "$worktrees_file")"
  while IFS='|' read -r wt_name wt_path; do
    [[ -z "$wt_name" || -z "$wt_path" ]] && continue
    [[ -d "$wt_path" ]] || warnings+="worktree path missing: ${wt_name} -> ${wt_path}\n"
  done < <(jq -r '.worktrees[]? | select((.worktree_path // "") != "" and (.status // "active") != "missing") | "\(.worktree_name)|\(.worktree_path)"' "$worktrees_file")

  errors=""
  if [[ -n "$invalid_status" ]]; then
    while IFS= read -r line; do
      [[ -n "$line" ]] && errors+="invalid flow status: $line\n"
    done <<< "$invalid_status"
  fi

  errors_json="$(printf '%b' "$errors" | sed '/^$/d' | _vibe_check_lines_to_json_array)"
  warnings_json="$(printf '%b' "$warnings" | sed '/^$/d' | _vibe_check_lines_to_json_array)"

  if [[ "$(echo "$errors_json" | jq 'length')" -gt 0 ]]; then
    group_status="fail"
    summary="flow audit found invalid persisted status"
  else
    group_status="pass"
    summary="flow audit passed"
  fi

  _vibe_check_group_json "$group_status" "$summary" "$errors_json" "$warnings_json"
}

_vibe_check_group_link() {
  local common_dir reg_file roadmap_file worktrees_file
  local task_ids_json item_ids_json wt_names_json
  local errors errors_json group_status summary

  common_dir="$(_vibe_check_common_dir)"
  [[ -n "$common_dir" ]] || { _vibe_check_group_json "fail" "not in git repo" '["Not in a git repository"]' '[]'; return; }

  reg_file="$common_dir/vibe/registry.json"
  roadmap_file="$common_dir/vibe/roadmap.json"
  worktrees_file="$common_dir/vibe/worktrees.json"

  [[ -f "$reg_file" ]] || { _vibe_check_group_json "fail" "missing registry.json" '["Missing registry.json"]' '[]'; return; }
  [[ -f "$roadmap_file" ]] || { _vibe_check_group_json "fail" "missing roadmap.json" '["Missing roadmap.json"]' '[]'; return; }
  [[ -f "$worktrees_file" ]] || { _vibe_check_group_json "fail" "missing worktrees.json" '["Missing worktrees.json"]' '[]'; return; }

  task_ids_json="$(jq -c '[.tasks[]?.task_id]' "$reg_file")"
  item_ids_json="$(jq -c '[.items[]?.roadmap_item_id]' "$roadmap_file")"
  wt_names_json="$(jq -c '[.worktrees[]?.worktree_name]' "$worktrees_file")"

  errors=""

  while IFS= read -r line; do
    [[ -n "$line" ]] && errors+="roadmap links missing task: $line\n"
  done < <(jq -r --argjson task_ids "$task_ids_json" '.items[]? | .roadmap_item_id as $rid | (.linked_task_ids // [])[]? | select($task_ids | index(.) | not) | "\($rid):\(.)"' "$roadmap_file" 2>/dev/null)

  while IFS= read -r line; do
    [[ -n "$line" ]] && errors+="roadmap item missing task back-link: $line\n"
  done < <(jq -r '
    $tasks[0] as $tasks
    | $roadmap[0] as $roadmap
    | $tasks.tasks[]? as $task
    | ($task.roadmap_item_ids // [])[]? as $rid
    | select(($roadmap.items | map(.roadmap_item_id) | index($rid)) != null)
    | select(([$roadmap.items[]? | select(.roadmap_item_id == $rid) | (.linked_task_ids // [])[]?] | index($task.task_id)) == null)
    | "\($rid):\($task.task_id)"
  ' --slurpfile tasks "$reg_file" --slurpfile roadmap "$roadmap_file" -n 2>/dev/null)

  while IFS= read -r line; do
    [[ -n "$line" ]] && errors+="task links missing roadmap item: $line\n"
  done < <(jq -r --argjson item_ids "$item_ids_json" '.tasks[]? | .task_id as $tid | (.roadmap_item_ids // [])[]? | select($item_ids | index(.) | not) | "\($tid):\(.)"' "$reg_file" 2>/dev/null)

  while IFS= read -r line; do
    [[ -n "$line" ]] && errors+="task missing roadmap back-link: $line\n"
  done < <(jq -r '
    $tasks[0] as $tasks
    | $roadmap[0] as $roadmap
    | $roadmap.items[]? as $item
    | ($item.linked_task_ids // [])[]? as $tid
    | select(($tasks.tasks | map(.task_id) | index($tid)) != null)
    | select(([$tasks.tasks[]? | select(.task_id == $tid) | (.roadmap_item_ids // [])[]?] | index($item.roadmap_item_id)) == null)
    | "\($tid):\($item.roadmap_item_id)"
  ' --slurpfile tasks "$reg_file" --slurpfile roadmap "$roadmap_file" -n 2>/dev/null)

  while IFS= read -r line; do
    [[ -n "$line" ]] && errors+="runtime points to missing worktree: $line\n"
  done < <(jq -r --argjson wt_names "$wt_names_json" '.tasks[]? | (.runtime_worktree_name // "") as $wt | select($wt != "") | select($wt_names | index($wt) | not) | "\(.task_id):\($wt)"' "$reg_file" 2>/dev/null)

  while IFS= read -r line; do
    [[ -n "$line" ]] && errors+="completed/archived task still has runtime binding: $line\n"
  done < <(jq -r '.tasks[]? | select((.status == "completed" or .status == "archived") and ((.runtime_worktree_name != null) or (.runtime_worktree_path != null) or (.runtime_branch != null) or (.runtime_agent != null))) | .task_id' "$reg_file" 2>/dev/null)

  errors_json="$(printf '%b' "$errors" | sed '/^$/d' | _vibe_check_lines_to_json_array)"

  if [[ "$(echo "$errors_json" | jq 'length')" -gt 0 ]]; then
    group_status="fail"
    summary="link check failed"
  else
    group_status="pass"
    summary="link check passed"
  fi

  _vibe_check_group_json "$group_status" "$summary" "$errors_json" '[]'
}

_vibe_check_group_json_file() {
  local file="$1" base errors warnings group_status summary
  local errors_json warnings_json

  [[ -f "$file" ]] || { _vibe_check_group_json "fail" "file missing" "[\"File not found: $file\"]" '[]'; return; }
  jq empty "$file" >/dev/null 2>&1 || { _vibe_check_group_json "fail" "invalid json" "[\"Invalid JSON: $file\"]" '[]'; return; }

  base="$(basename "$file")"
  errors=""

  case "$base" in
    registry.json)
      jq -e 'type == "object" and has("schema_version") and has("tasks") and (.tasks | type == "array")' "$file" >/dev/null 2>&1 || errors+="registry root shape invalid\n"
      while IFS= read -r line; do
        [[ -n "$line" ]] && errors+="registry required fields missing: $line\n"
      done < <(jq -r 'def req:["task_id","title","status","source_type","source_refs","roadmap_item_ids","issue_refs","related_task_ids","subtasks","created_at","updated_at"]; .tasks[]? | .task_id as $id | (req - (keys)) as $m | select($m|length>0) | "\($id):\($m|join(","))"' "$file")
      while IFS= read -r line; do
        [[ -n "$line" ]] && errors+="registry invalid status: $line\n"
      done < <(jq -r '.tasks[]? | select((.status | IN("todo","in_progress","blocked","completed","archived")) | not) | "\(.task_id):\(.status)"' "$file")
      while IFS= read -r line; do
        [[ -n "$line" ]] && errors+="registry invalid source_type: $line\n"
      done < <(jq -r '.tasks[]? | select((.source_type | IN("issue","local","openspec")) | not) | "\(.task_id):\(.source_type // "null")"' "$file")
      ;;
    roadmap.json)
      jq -e 'type == "object" and has("schema_version") and has("version_goal") and has("items") and (.items | type == "array")' "$file" >/dev/null 2>&1 || errors+="roadmap root shape invalid\n"
      while IFS= read -r line; do
        [[ -n "$line" ]] && errors+="roadmap required fields missing: $line\n"
      done < <(jq -r 'def req:["roadmap_item_id","title","status","source_type","source_refs","issue_refs","linked_task_ids","created_at","updated_at"]; .items[]? | .roadmap_item_id as $id | (req - (keys)) as $m | select($m|length>0) | "\($id):\($m|join(","))"' "$file")
      while IFS= read -r line; do
        [[ -n "$line" ]] && errors+="roadmap invalid status: $line\n"
      done < <(jq -r '.items[]? | select((.status | IN("p0","current","next","deferred","rejected")) | not) | "\(.roadmap_item_id):\(.status)"' "$file")
      while IFS= read -r line; do
        [[ -n "$line" ]] && errors+="roadmap invalid source_type: $line\n"
      done < <(jq -r '.items[]? | select((.source_type | IN("github","local")) | not) | "\(.roadmap_item_id):\(.source_type // "null")"' "$file")
      ;;
    worktrees.json)
      jq -e 'type == "object" and has("schema_version") and has("worktrees") and (.worktrees | type == "array")' "$file" >/dev/null 2>&1 || errors+="worktrees root shape invalid\n"
      while IFS= read -r line; do
        [[ -n "$line" ]] && errors+="worktrees invalid status: $line\n"
      done < <(jq -r '.worktrees[]? | select((.status // "active" | IN("active","idle","missing","stale")) | not) | "\(.worktree_name):\(.status // "null")"' "$file")
      ;;
    *)
      warnings+="no strict schema for file: $base\n"
      ;;
  esac

  errors_json="$(printf '%b' "$errors" | sed '/^$/d' | _vibe_check_lines_to_json_array)"
  warnings_json="$(printf '%b' "$warnings" | sed '/^$/d' | _vibe_check_lines_to_json_array)"

  if [[ "$(echo "$errors_json" | jq 'length')" -gt 0 ]]; then
    group_status="fail"
    summary="json/schema check failed"
  else
    group_status="pass"
    summary="json/schema check passed"
  fi

  _vibe_check_group_json "$group_status" "$summary" "$errors_json" "$warnings_json"
}

_vibe_check_group_docs() {
  local -a missing_frontmatter
  local file first_line total checked
  local warnings_json summary

  if [[ ! -d docs ]]; then
    _vibe_check_group_json "pass" "docs directory not found" '[]' '[]'
    return
  fi

  while IFS= read -r file; do
    checked=$((checked + 1))
    first_line="$(sed -n '1p' "$file" 2>/dev/null)"
    if [[ "$first_line" != "---" ]]; then
      missing_frontmatter+=("$file")
    fi
  done < <(find docs -type f -name '*.md' 2>/dev/null)

  total=${#missing_frontmatter[@]}
  if [[ "$total" -gt 0 ]]; then
    warnings_json="$(printf '%s\n' "${missing_frontmatter[@]:0:20}" | _vibe_check_lines_to_json_array | jq 'map("missing frontmatter: " + .)')"
    summary="docs check warnings: ${total} files missing frontmatter (showing first 20)"
  else
    warnings_json='[]'
    summary="docs check passed (${checked:-0} files scanned)"
  fi

  _vibe_check_group_json "pass" "$summary" '[]' "$warnings_json"
}
