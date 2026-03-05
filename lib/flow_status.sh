#!/usr/bin/env zsh
# lib/flow_status.sh - Status and Detection for Flow module

_detect_feature() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }; return 1; }
_detect_agent() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }; echo "claude"; }

# Show status for current or specified feature
_flow_status() {
  setopt localoptions typeset_silent 2>/dev/null || true
  local json_out=0
  [[ "${1:-}" == "--json" ]] && { json_out=1; shift; }

  local feature="${1:-}"
  local current_wt; current_wt=$(basename "$PWD")

  # Check if we're in a git repository
  local worktrees_file registry_file
  local git_common_dir
  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || {
    log_error "Not in a worktree"
    return 1
  }
  worktrees_file="$git_common_dir/vibe/worktrees.json"
  registry_file="${git_common_dir}/vibe/registry.json"

  # Identify tasks to show
  local -a tasks_to_show
  local cur_t
  if [[ -z "$feature" ]]; then
    local wt_data; wt_data=$(jq -c --arg wt "$current_wt" '.worktrees[]? | select(.worktree_name == $wt)' "$worktrees_file" 2>/dev/null)
    cur_t=$(echo "$wt_data" | jq -r '.current_task // empty')
    local other_ts; other_ts=($(echo "$wt_data" | jq -r '.tasks[]? // empty' 2>/dev/null))
    
    [[ -n "$cur_t" ]] && tasks_to_show+=("$cur_t")
    for t in "${other_ts[@]}"; do
        [[ "$t" == "$cur_t" ]] && continue
        [[ ${#tasks_to_show[@]} -ge 6 ]] && break
        tasks_to_show+=("$t")
    done
    [[ ${#tasks_to_show[@]} -eq 0 ]] && { log_error "No task bound to current worktree"; return 1; }
  else
    tasks_to_show=("$feature")
    cur_t="$feature"
  fi

  if (( json_out )); then
    # JSON output mode (for programmatic use)
    local task_outputs=()
    local found_requested_feature=0
    for tid in "${tasks_to_show[@]}"; do
      local task_data; task_data=$(jq -e --arg tid "$tid" '.tasks[]? | select(.task_id == $tid)' "$registry_file" 2>/dev/null)
      if [[ -n "$task_data" ]]; then
        task_outputs+=("$(echo "$task_data" | jq -c '{task_id, title, status, next_step, assigned_worktree}')")
        [[ "$tid" == "$feature" ]] && found_requested_feature=1
      fi
    done
    if [[ -n "$feature" && $found_requested_feature -eq 0 ]]; then
        log_error "Requested task not found: $feature"
        return 1
    fi
    printf '%s\n' "${task_outputs[@]}" | jq -s '{"tasks": .}'
    return 0
  fi

  # Human-readable output loop
  local idx=0
  local has_requested_feature=0
  [[ -n "$feature" ]] && has_requested_feature=1
  local found_requested_feature=0

  for tid in "${tasks_to_show[@]}"; do
    local task_data="$(jq -e --arg tid "$tid" '.tasks[]? | select(.task_id == $tid)' "$registry_file" 2>/dev/null)"
    if [[ -z "$task_data" ]]; then
      log_warn "Task not found in registry: $tid"
      continue
    fi
    [[ "$tid" == "$feature" ]] && found_requested_feature=1

    local title="$(echo "$task_data" | jq -r '.title // "N/A"')"
    local task_status="$(echo "$task_data" | jq -r '.status // "unknown"')"
    local next_step="$(echo "$task_data" | jq -r '.next_step // "N/A"')"
    local worktree="$(echo "$task_data" | jq -r '.assigned_worktree // "none"')"
    local agent="$(echo "$task_data" | jq -r '.agent // "none"')"
    local subtask_id="$(echo "$task_data" | jq -r '.current_subtask_id // empty')"

    # Supervisor Lifecycle Detection
    local phase="${CYAN}Draft${NC}" gate_num="" gate_label=""
    if [[ "$next_step" =~ "Gate ([0-6])" ]]; then
        gate_num="${match[1]}"
        case "$gate_num" in
            0|1|2|3) phase="${YELLOW}Discuss (Planning)${NC}" ;;
            4|5)     phase="${GREEN}Execute (Implementation)${NC}" ;;
            6)       phase="${MAGENTA}Review (Audit)${NC}" ;;
        esac
        gate_label="Gate $gate_num"
    fi

    # Identity Check
    local current_actor="$(git config user.name 2>/dev/null || echo "unknown")"
    local actor_label="${BOLD}${current_actor}${NC}"
    [[ "$current_actor" != "$agent" && "$agent" != "none" ]] && actor_label="${YELLOW}${current_actor} (${agent} assigned)${NC}"

    local header_label="${CYAN}${BOLD}任务 $[idx+1]${NC}"
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

  # Physical status
  local dirty_count; dirty_count=$(git status --porcelain | wc -l | xargs)
  echo "${CYAN}Physical Status:${NC} $dirty_count dirty files"
  git status --short
  echo ""

  # File metrics
  echo "${CYAN}File Metrics:${NC}"
  local total_loc; total_loc=$(find "$VIBE_ROOT/lib" "$VIBE_ROOT/bin" -name '*.sh' -o -name 'vibe' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
  echo "  Total LOC (lib/ + bin/): ${total_loc:-0} / 1800"

  local flow_loc; flow_loc=$(wc -l < "$VIBE_ROOT/lib/flow.sh" 2>/dev/null || echo 0)
  echo "  lib/flow.sh: $flow_loc lines"

  local flow_status_loc; flow_status_loc=$(wc -l < "$VIBE_ROOT/lib/flow_status.sh" 2>/dev/null || echo 0)
  echo "  lib/flow_status.sh: $flow_status_loc lines"
}

# List all worktrees with their status
_flow_list() {
  setopt localoptions typeset_silent 2>/dev/null || true
  local current_wt; current_wt=$(basename "$PWD")
  local shared_dir; shared_dir="$(_flow_shared_dir)"
  local shared_count; shared_count=$(ls -1 "$shared_dir" 2>/dev/null | wc -l | xargs)
  local worktrees_file; worktrees_file="$(git rev-parse --git-common-dir)/vibe/worktrees.json"
  local registry_file; registry_file="$(_flow_registry_file)"

  echo "${BOLD}${CYAN}Worktree Landscape:${NC}"
  echo ""

  while read -r wt_path; do
    local wt_name=$(basename "$wt_path")
    local d_count=$(git -C "$wt_path" status --porcelain 2>/dev/null | wc -l | xargs)
    local indicator="${GREEN}clean${NC}"
    [[ "$d_count" -gt 0 ]] && indicator="${YELLOW}$d_count dirty files${NC}"

    local wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
    local cur_t wt_tasks_raw
    cur_t=$(jq -r --arg n "$wt_name" '.worktrees[]? | select(.worktree_name == $n) | .current_task // empty' "$worktrees_file" 2>/dev/null)
    wt_tasks_raw=$(jq -r --arg n "$wt_name" '.worktrees[]? | select(.worktree_name == $n) | .tasks[]?' "$worktrees_file" 2>/dev/null)
    local -a wt_tasks; wt_tasks=(${(f)wt_tasks_raw})
    
    local -a sorted_tasks
    [[ -n "$cur_t" ]] && sorted_tasks+=("$cur_t")
    for t in "${wt_tasks[@]}"; do
      [[ "$t" == "$cur_t" ]] && continue
      [[ ${#sorted_tasks[@]} -ge 6 ]] && break
      sorted_tasks+=("$t")
    done

    local marker=""
    [[ "$wt_name" == "$current_wt" ]] && marker=" ${BOLD}(current)${NC}"

    printf "${BOLD}%s${NC}%s\n" "$wt_name" "$marker"
    printf "  Branch: %s\n" "${wt_branch:-N/A}"
    printf "  Status: %b\n" "$indicator"
    
    if [[ ${#sorted_tasks[@]} -gt 0 ]]; then
      for tid in "${sorted_tasks[@]}"; do
        local t_status t_next
        t_status=$(jq -r --arg tid "$tid" '.tasks[]? | select(.task_id == $tid) | .status // "unknown"' "$registry_file" 2>/dev/null)
        t_next=$(jq -r --arg tid "$tid" '.tasks[]? | select(.task_id == $tid) | .next_step // "N/A"' "$registry_file" 2>/dev/null | head -c 50)
        [[ ${#t_next} -eq 50 ]] && t_next="${t_next}..."
        
        local prefix="  [Sub ]"
        [[ "$tid" == "$cur_t" ]] && prefix="  [Main]"
        printf "%s %s (%s)\n" "$prefix" "$tid" "$t_status"
        [[ "$tid" == "$cur_t" ]] && printf "         Next: %s\n" "$t_next"
      done
    else
      printf "  Task: none\n"
    fi
    echo ""
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')

  [[ "$shared_count" -gt 0 ]] && echo "${CYAN}Shared Context:${NC} $shared_count files in .git/vibe/shared" || true
}
