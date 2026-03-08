#!/usr/bin/env zsh
# lib/flow_status.sh - Status and metrics for flow module

[[ -f "$VIBE_LIB/flow_list.sh" ]] && source "$VIBE_LIB/flow_list.sh"

_detect_feature() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }; return 1; }
_detect_agent() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }; echo "claude"; }
_normalize_actor_name() { local name="${1:l}"; echo "${name#agent-}"; }

_flow_print_metrics() {
  local total_loc=0
  local -a oversized_files
  local f lines rel

  for f in "$VIBE_ROOT"/lib/*.sh "$VIBE_ROOT"/bin/vibe; do
    [[ -f "$f" ]] || continue
    lines=$(wc -l < "$f" 2>/dev/null || echo 0)
    total_loc=$((total_loc + lines))
    if (( lines > 200 )); then
      rel="${f#$VIBE_ROOT/}"
      oversized_files+=("$rel|$lines")
    fi
  done

  echo "${CYAN}File Metrics:${NC}"
  echo "  Total LOC (lib/ + bin/): ${total_loc:-0} / 4800"

  local flow_loc flow_status_loc
  flow_loc=$(wc -l < "$VIBE_ROOT/lib/flow.sh" 2>/dev/null || echo 0)
  flow_status_loc=$(wc -l < "$VIBE_ROOT/lib/flow_status.sh" 2>/dev/null || echo 0)
  echo "  lib/flow.sh: $flow_loc lines"
  echo "  lib/flow_status.sh: $flow_status_loc lines"

  if [[ ${#oversized_files[@]} -eq 0 ]]; then
    echo "  Oversize Files (>200): none"
    return 0
  fi

  echo "  Oversize Files (>200):"
  local entry file_name file_lines
  for entry in "${oversized_files[@]}"; do
    file_name=$(echo "$entry" | cut -d'|' -f1)
    file_lines=$(echo "$entry" | cut -d'|' -f2)
    echo "    - $file_name: $file_lines lines"
  done
}

_flow_status() {
  setopt localoptions typeset_silent 2>/dev/null || true

  local json_out=0
  [[ "${1:-}" == "--json" ]] && { json_out=1; shift; }

  local feature="${1:-}"
  local current_wt git_common_dir worktrees_file registry_file
  current_wt=$(basename "$PWD")

  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || {
    log_error "Not in a worktree"
    return 1
  }

  worktrees_file="$git_common_dir/vibe/worktrees.json"
  registry_file="$git_common_dir/vibe/registry.json"

  local -a tasks_to_show
  local cur_t=""
  if [[ -z "$feature" ]]; then
    local wt_data t
    wt_data=$(jq -c --arg wt "$current_wt" '.worktrees[]? | select(.worktree_name == $wt)' "$worktrees_file" 2>/dev/null)
    cur_t=$(echo "$wt_data" | jq -r '.current_task // empty')
    [[ -n "$cur_t" ]] && tasks_to_show+=("$cur_t")
    while IFS= read -r t; do
      [[ -z "$t" || "$t" == "$cur_t" ]] && continue
      [[ ${#tasks_to_show[@]} -ge 6 ]] && break
      tasks_to_show+=("$t")
    done < <(echo "$wt_data" | jq -r '.tasks[]? // empty' 2>/dev/null)
    [[ ${#tasks_to_show[@]} -eq 0 ]] && { log_error "No task bound to current worktree"; return 1; }
  else
    tasks_to_show=("$feature")
    cur_t="$feature"
  fi

  if (( json_out )); then
    local -a task_outputs
    local found_requested_feature=0 tid task_data
    for tid in "${tasks_to_show[@]}"; do
      task_data=$(jq -e --arg tid "$tid" '.tasks[]? | select(.task_id == $tid)' "$registry_file" 2>/dev/null)
      [[ -z "$task_data" ]] && continue
      task_outputs+=("$(echo "$task_data" | jq -c '{task_id, title, status, next_step, assigned_worktree}')")
      [[ "$tid" == "$feature" ]] && found_requested_feature=1
    done
    if [[ -n "$feature" && $found_requested_feature -eq 0 ]]; then
      log_error "Requested task not found: $feature"
      return 1
    fi
    printf '%s\n' "${task_outputs[@]}" | jq -s '{"tasks": .}'
    return 0
  fi

  local idx=0 has_requested_feature=0 found_requested_feature=0 tid
  [[ -n "$feature" ]] && has_requested_feature=1

  for tid in "${tasks_to_show[@]}"; do
    local task_data title task_status next_step worktree agent subtask_id
    task_data="$(jq -e --arg tid "$tid" '.tasks[]? | select(.task_id == $tid)' "$registry_file" 2>/dev/null)"
    [[ -z "$task_data" ]] && { log_warn "Task not found in registry: $tid"; continue; }
    [[ "$tid" == "$feature" ]] && found_requested_feature=1

    title="$(echo "$task_data" | jq -r '.title // "N/A"')"
    task_status="$(echo "$task_data" | jq -r '.status // "unknown"')"
    next_step="$(echo "$task_data" | jq -r '.next_step // "N/A"')"
    worktree="$(echo "$task_data" | jq -r '.assigned_worktree // "none"')"
    agent="$(echo "$task_data" | jq -r '.agent // "none"')"
    subtask_id="$(echo "$task_data" | jq -r '.current_subtask_id // empty')"

    local phase="${CYAN}Draft${NC}" gate_num="" gate_label=""
    if [[ "$next_step" =~ "Gate ([0-6])" ]]; then
      gate_num="${match[1]}"
      case "$gate_num" in
        0|1|2|3) phase="${YELLOW}Discuss (Planning)${NC}" ;;
        4|5) phase="${GREEN}Execute (Implementation)${NC}" ;;
        6) phase="${MAGENTA}Review (Audit)${NC}" ;;
      esac
      gate_label="Gate $gate_num"
    fi

    local current_actor agent_assigned actor_label header_label
    current_actor="$(echo "$task_data" | jq -r '.agent_log.latest_actor // .runtime_agent // .agent // "unknown"')"
    agent_assigned="$(echo "$task_data" | jq -r '.assigned_worktree // "none"')"
    actor_label="${BOLD}${current_actor}${NC}"

    header_label="${CYAN}${BOLD}任务 $((idx + 1))${NC}"
    [[ "$tid" == "$cur_t" ]] && header_label="${GREEN}${BOLD}重点任务 (Main)${NC}"

    echo "$header_label ──────────────────────────────────────────"
    echo "${BOLD}ID:${NC}      $tid"
    echo "${BOLD}标题:${NC}    $title"
    echo "──────────────────────────────────────────────────"
    echo "${BOLD}阶段:${NC}    $phase ${gate_label:+( $gate_label )}"
    echo "${BOLD}执行:${NC}    $actor_label"
    echo "${BOLD}状态:${NC}    $task_status${subtask_id:+ ($subtask_id)}"
    echo "──────────────────────────────────────────────────"
    echo "${BOLD}下一步:${NC}  $next_step"
    echo "──────────────────────────────────────────────────"
    echo ""
    idx=$((idx + 1))
  done

  if [[ $has_requested_feature -eq 1 && $found_requested_feature -eq 0 ]]; then
    log_error "Requested task not found: $feature"
    return 1
  fi

  local dirty_count
  dirty_count=$(git status --porcelain | wc -l | xargs)
  echo "${CYAN}Physical Status:${NC} $dirty_count dirty files"
  git status --short
  echo ""
  _flow_print_metrics
}
