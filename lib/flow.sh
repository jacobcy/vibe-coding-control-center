#!/usr/bin/env zsh
[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }

_detect_feature() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }; return 1; }
_detect_agent() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }; echo "claude"; }
_flow_registry_file() { echo "$(git rev-parse --git-common-dir)/vibe/registry.json"; }
_flow_task_title() { jq -r --arg task_id "$1" '.tasks[]? | select(.task_id == $task_id) | .title // empty' "$2"; }
_flow_set_identity() { git config user.name "$1" 2>/dev/null || git config user.name "$1" || return 1; git config user.email "$1@vibe.coding" 2>/dev/null || git config user.email "$1@vibe.coding"; }
_flow_start_usage() { echo "Usage: vibe flow start <feature> | --task <task-id> [--agent=claude] [--base=main]"; }
_flow_default_agent() { _detect_agent 2>/dev/null || echo "${VIBE_AGENT:-claude}"; }
_flow_require_clean_worktree() { [[ -z "$(git status --porcelain 2>/dev/null)" ]] || { log_error "Refusing to start task from dirty worktree"; return 1; }; }
_flow_require_base_ref() { git fetch origin "$1" --quiet 2>/dev/null || true; git show-ref --verify --quiet "refs/remotes/origin/$1" || { log_error "origin/$1 not found"; return 1; }; }
_flow_branch_exists() { git show-ref --verify --quiet "refs/heads/$1" || git show-ref --verify --quiet "refs/remotes/origin/$1" || git ls-remote --exit-code --heads origin "$1" >/dev/null 2>&1; }

_flow_shared_dir() { local d; d="$(git rev-parse --git-common-dir)/vibe/shared"; mkdir -p "$d"; echo "$d"; }

_flow_start_worktree() {
  local feature="$1" agent="$2" base="$3" wt_dir="wt-${agent}-${feature}" branch="${agent}/${feature}"
  log_step "Creating worktree $wt_dir"
  if typeset -f wtnew &>/dev/null; then
    wtnew "$feature" "$agent" "$base" || { log_error "wtnew failed"; return 1; }
  else
    git fetch origin "$base" --quiet 2>/dev/null || true
    git worktree add -b "$branch" "../$wt_dir" "$base" || { log_error "git worktree add failed"; return 1; }
    cd "../$wt_dir" || return 1
  fi
  _flow_set_identity "$agent" || return 1
  log_success "Environment ready. Use /vibe-new $feature to start."
}

_flow_is_main_worktree() {
  local dir; dir=$(basename "$PWD")
  [[ "$dir" =~ ^wt-[^-]+-.+$ ]] && return 1 || return 0
}

_flow_start_task() {
  local task_id="$1" agent="$2" base="$3" registry_file title branch
  vibe_require git jq || return 1
  _flow_is_main_worktree && { log_error "Run this inside a feature worktree or use vibe flow new"; return 1; }

  registry_file="$(_flow_registry_file)"; [[ -f "$registry_file" ]] || { log_error "No registry found"; return 1; }
  title="$(_flow_task_title "$task_id" "$registry_file")"
  if [[ -z "$title" ]]; then
    vibe_task add "$task_id" --title "Task started via flow" >/dev/null 2>&1
  fi
  
  _flow_require_clean_worktree || return 1
  _flow_require_base_ref "$base" || return 1
  branch="${agent}/${task_id}"
  git checkout -b "$branch" "origin/$base" || return 1
  _flow_set_identity "$agent" || return 1
  log_success "Started task: $task_id"
}

_flow_start() {
  local feature="" task_id="" agent="" base="main" arg
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_start_usage; return 0; }; done
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --task) task_id="$2"; shift 2 ;;
      --agent) agent="$2"; shift 2 ;;
      --base) base="$2"; shift 2 ;;
      *) [[ -z "$feature" ]] && feature="$1"; shift ;;
    esac
  done
  [[ -n "$task_id" ]] && { _flow_start_task "$task_id" "${agent:-claude}" "$base"; return $?; }
  _flow_start_worktree "${feature:-new-feat}" "${agent:-claude}" "$base"
}

_flow_usage() {
  echo "${BOLD}Vibe Flow Manager${NC}"
  echo ""
  echo "Usage: ${CYAN}vibe flow <subcommand>${NC} [args]"
  echo ""
  echo "Subcommands:"
  echo "  ${GREEN}new${NC} <feature> [--agent <name>] [--base <ref>]   创建新沙盒环境"
  echo "  ${GREEN}done${NC} [<feature>]                              结项并彻底清理物理环境"
  echo "  ${GREEN}status${NC} [<feature>]                            查看沙盒状态与物理变动"
  echo "  ${GREEN}sync${NC}                                          同步当前变更至所有 Worktree"
  echo ""
  echo "Options for 'new':"
  echo "  --agent <name>    指定 AI 身份 (默认: claude)"
  echo "  --base <ref>      指定基础分支 (默认: main)"
}

_flow_done() {
  local feature="${1:-$(_detect_feature || true)}" wt_dir main_dir branch
  wt_dir=$(basename "$PWD")
  branch=$(git branch --show-current)
  
  log_warn "WARNING: This will PERMANENTLY delete the physical worktree and local branch."
  confirm_action "Proceed with cleanup?" || return 0

  # 1. Cleanup Worktree (Physical layer only)
  main_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); main_dir="${main_dir%/.git}"; 
  cd "$main_dir" || return 1
  git worktree remove "../$wt_dir" --force 2>/dev/null || true
  
  # 2. Branch cleanup
  if [[ -n "$branch" && "$branch" != "main" ]]; then
    git push origin --delete "$branch" 2>/dev/null || true
    git branch -D "$branch" 2>/dev/null || true
  fi
  log_success "Worktree and branch cleaned."
}

_flow_sync() {
  local current_branch=$(git branch --show-current 2>/dev/null)
  while read -r wt_path; do
    git -C "$wt_path" merge "$current_branch" --no-edit >/dev/null 2>&1 || true
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')
  log_success "Branches synced."
}

_flow_status() {
  local json_out=0
  [[ "${1:-}" == "--json" ]] && { json_out=1; shift; }

  local feature="${1:-$(_detect_feature || true)}"
  local current_wt; current_wt=$(basename "$PWD")
  local shared_dir; shared_dir="$(_flow_shared_dir)"
  local shared_count; shared_count=$(ls -1 "$shared_dir" 2>/dev/null | wc -l | xargs)

  if (( json_out )); then
    local wts_json="[]"
    while read -r wt_path; do
      local wt_name=$(basename "$wt_path")
      local is_dirty=0
      [[ -n "$(git -C "$wt_path" status --porcelain 2>/dev/null)" ]] && is_dirty=1
      local wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
      wts_json=$(echo "$wts_json" | jq --arg n "$wt_name" --arg p "$wt_path" --arg b "$wt_branch" --argjson d "$is_dirty" \
        '. += [{"name":$n, "path":$p, "branch":$b, "is_dirty":$d}]')
    done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')
    
    jq -n --arg f "$feature" --arg c "$current_wt" --argjson w "$wts_json" --argjson s "$shared_count" \
      '{current_feature: $f, current_worktree: $c, worktrees: $w, shared_context_count: $s}'
    return 0
  fi

  local dirty_count; dirty_count=$(git status --porcelain | wc -l | xargs)
  echo "${BOLD}Task:${NC} $feature | ${BOLD}Branch:${NC} $(git branch --show-current 2>/dev/null)"
  echo "${CYAN}Physical Status:${NC} $dirty_count dirty files found (current)."
  
  # Cross-worktree scan
  echo "${CYAN}Worktree Landscape:${NC}"
  while read -r wt_path; do
    local wt_name=$(basename "$wt_path")
    local d_count=$(git -C "$wt_path" status --porcelain 2>/dev/null | wc -l | xargs)
    local indicator="${GREEN}clean${NC}"
    [[ "$d_count" -gt 0 ]] && indicator="${YELLOW}$d_count dirty files${NC}"
    [[ "$wt_name" == "$current_wt" ]] && wt_name="${BOLD}${wt_name}${NC} (current)"
    printf "  - %-30s %b\n" "$wt_name" "$indicator"
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')

  [[ "$shared_count" -gt 0 ]] && echo "${CYAN}Shared Context:${NC} $shared_count files in .git/vibe/shared"
  
  git status --short
}

vibe_flow() {
  case "${1:-help}" in
    start|new) shift; _flow_start "$@" ;;
    done)      shift; _flow_done "$@" ;;
    status)    shift; _flow_status "$@" ;;
    sync)      _flow_sync ;;
    help|-h|--help) _flow_usage ;;
    *) _flow_usage ;;
  esac
}


