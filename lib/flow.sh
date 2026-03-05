#!/usr/bin/env zsh
[[ -z "${VIBE_ROOT:-}" ]] && { echo "error: VIBE_ROOT not set"; return 1; }
source "$VIBE_LIB/flow_help.sh"
source "$VIBE_LIB/flow_status.sh"
source "$VIBE_LIB/task.sh"

_flow_registry_file() { echo "$(git rev-parse --git-common-dir)/vibe/registry.json"; }
_flow_task_title() { jq -r --arg task_id "$1" '.tasks[]? | select(.task_id == $task_id) | .title // empty' "$2"; }
_flow_set_identity() { git config user.name "$1" 2>/dev/null || git config user.name "$1" || return 1; git config user.email "$1@vibe.coding" 2>/dev/null || git config user.email "$1@vibe.coding"; }
_flow_default_agent() { _detect_agent 2>/dev/null || echo "${VIBE_AGENT:-claude}"; }
_flow_require_clean_worktree() { [[ -z "$(git status --porcelain 2>/dev/null)" ]] || { log_error "Refusing to start task from dirty worktree"; return 1; }; }
_flow_require_base_ref() { git fetch origin "$1" --quiet 2>/dev/null || true; git show-ref --verify --quiet "refs/remotes/origin/$1" || { log_error "origin/$1 not found"; return 1; }; }
_flow_branch_exists() { git show-ref --verify --quiet "refs/heads/$1" || git show-ref --verify --quiet "refs/remotes/origin/$1" || git ls-remote --exit-code --heads origin "$1" >/dev/null 2>&1; }
_flow_shared_dir() { local d; d="$(git rev-parse --git-common-dir)/vibe/shared"; mkdir -p "$d"; echo "$d"; }
_flow_is_main_worktree() { local d; d=$(basename "$PWD"); [[ "$d" =~ ^wt-[^-]+-.+$ ]] && return 1 || return 0; }

_flow_new_worktree() {
  local feature="$1" agent="$2" ref="$3" repo_root wt_dir wt_path registry_file task_id
  vibe_require git jq || return 1
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || { log_error "Not in a git repo"; return 1; }
  wt_dir="wt-${agent}-${feature}"; wt_path="${repo_root:h}/$wt_dir"; [[ -e "$wt_path" ]] && { log_error "Worktree already exists: $wt_dir (use 'wt $wt_dir' to enter)"; return 1; }
  registry_file="$(_flow_registry_file)"; task_id="$(_vibe_task_today)-$(_vibe_task_slugify "$feature")"
  [[ -f "$registry_file" ]] && jq -e --arg tid "$task_id" '.tasks[]? | select(.task_id == $tid)' "$registry_file" >/dev/null 2>&1 && { log_error "Task already registered: $task_id (use 'vibe flow start --task $task_id' to resume)"; return 1; }
  log_step "Registering task: $feature → $task_id"; _vibe_task_add "$feature" || return 1
  log_step "Creating worktree: $wt_dir"
  if typeset -f wtnew &>/dev/null; then wtnew "$feature" "$agent" "$ref" || { log_error "wtnew failed"; return 1; }
  else git fetch origin "$ref" --quiet 2>/dev/null || true; git worktree add -b "${agent}/${feature}" "$wt_path" "$ref" || { log_error "git worktree add failed"; return 1; }; cd "$wt_path" || return 1
  fi
  log_step "Binding task $task_id to worktree"; _vibe_task_update "$task_id" --status "in_progress" --bind-current || return 1
  log_success "Feature ready: $feature  (task: $task_id)"; echo "💡 Next: Run ${CYAN}vup${NC} to open your cockpit."
}

_flow_new_task() {
  local task_id="$1" agent="$2" ref="$3" registry_file title branch
  vibe_require git jq || return 1
  registry_file="$(_flow_registry_file)"; title="$(_flow_task_title "$task_id" "$registry_file")"; [[ -n "$title" ]] || { log_error "Task not found: $task_id"; return 1; }
  _flow_require_clean_worktree || return 1; _flow_require_base_ref "$ref" || return 1; branch="${agent}/${task_id}"
  _flow_branch_exists "$branch" && { log_error "Target branch already exists: $branch"; return 1; }
  git checkout -b "$branch" "origin/$ref" || return 1; _flow_set_identity "$agent" || return 1; log_success "Started task: $task_id ($title)"
}

_flow_new() {
  local feature="" task_id="" agent="" ref="main" arg
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_new_usage; return 0; }; done
  while [[ $# -gt 0 ]]; do case "$1" in --task) task_id="$2"; shift 2 ;; --agent) agent="$2"; shift 2 ;; --branch|--base) ref="$2"; shift 2 ;; *) [[ -z "$feature" ]] && feature="$1"; shift ;; esac; done
  [[ -n "$task_id" && -z "$agent" ]] && agent="$(_flow_default_agent)"; [[ -z "$task_id" && -z "$agent" ]] && agent="${VIBE_AGENT:-claude}"
  if [[ -n "$task_id" && -z "$feature" ]]; then
    if ! _flow_is_main_worktree; then log_step "Binding task $task_id to current worktree"; _vibe_task_update "$task_id" --status "in_progress" --bind-current || return 1; return 0
    else _flow_new_task "$task_id" "${agent:-claude}" "$ref"; return $?
    fi
  fi
  [[ -n "$feature" ]] || { _flow_new_usage; return 1; }; _flow_new_worktree "$feature" "${agent:-claude}" "$ref"
}

_flow_done() {
  local wt_path wt_dir branch main_dir unmerged
  if [[ $(git branch --show-current) == "main" ]] || _flow_is_main_worktree; then log_warn "Current repository or branch is protected."; return 1; fi
  wt_path="$PWD"; wt_dir=$(basename "$wt_path"); branch=$(git branch --show-current)
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then log_error "Working directory is not clean. Please commit or stash changes before finishing."; return 1; fi
  git fetch origin main --quiet 2>/dev/null || true
  unmerged=$(git rev-list "origin/main..$branch" 2>/dev/null || echo "")
  if [[ -n "$unmerged" ]]; then log_error "Branch '$branch' has commits not merged into origin/main. Please open a PR and merge first."; return 1; fi
  log_warn "WARNING: This will clear contents of $wt_dir and PERMANENTLY delete local branch ($branch)."; confirm_action "Proceed with cleanup?" || return 0
  main_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null); main_dir="${main_dir%/.git}"; cd "$main_dir" || return 1
  [[ $(git ls-remote --exit-code --heads origin "$branch" 2>/dev/null) ]] && { log_step "Deleting remote branch: $branch"; git push origin --delete "$branch" 2>/dev/null || true; }
  log_step "Detaching worktree $wt_dir"; git worktree remove "$wt_path" --force 2>/dev/null || true; mkdir -p "$wt_path"
  log_step "Cleaning up local branch: $branch"; git branch -D "$branch" 2>/dev/null || true
  log_success "Cleanup complete."; echo "💡 Next: Run ${CYAN}vibe task list${NC} to check remaining tasks."
}

_flow_sync() {
  local current_branch has_fail=0 wt_branch behind
  current_branch=$(git branch --show-current 2>/dev/null); [[ -z "$current_branch" ]] && { log_error "Not in a git repository"; return 1; }
  while read -r wt_path; do
    wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null); [[ "$wt_branch" == "$current_branch" ]] && continue
    behind=$(git rev-list --count "$wt_branch".."$current_branch" 2>/dev/null || echo "0")
    [[ "$behind" -gt 0 ]] && git -C "$wt_path" merge "$current_branch" --no-edit >/dev/null 2>&1 || [[ "$behind" -gt 0 ]] && { log_error "Merge failed for $wt_branch"; has_fail=1; }
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')
  [[ "$has_fail" -eq 1 ]] && return 1; log_success "Branches synced."
}

_flow_pr() {
  local bump_type="" pr_title="" pr_body="" version_msg="" branch commit_logs first_msg open_prs
  while [[ $# -gt 0 ]]; do case "$1" in -h|--help) _flow_pr_usage; return 0 ;; --bump) bump_type="$2"; shift 2 ;; --title) pr_title="$2"; shift 2 ;; --body) pr_body="$2"; shift 2 ;; --msg) version_msg="$2"; shift 2 ;; *) shift ;; esac; done
  vibe_require git || return 1; branch=$(git branch --show-current); [[ "$branch" == "main" ]] && { log_error "Cannot create PR from main branch"; return 1; }
  commit_logs=$(git log main..HEAD --oneline); [[ -z "$commit_logs" ]] && { log_warn "No new commits since main. Nothing to PR."; return 1; }
  [[ -z "$bump_type" ]] && bump_type="patch"; [[ -z "$pr_title" ]] && pr_title=$(echo "$commit_logs" | head -n 1 | sed 's/^[a-f0-9]* //'); [[ -z "$pr_body" ]] && pr_body=$(echo "$commit_logs" | sed 's/^[a-f0-9]* / - /')
  if [[ -z "$version_msg" ]]; then first_msg=$(echo "$commit_logs" | tail -n 1 | sed 's/^[a-f0-9]* //'); version_msg="${first_msg} ..."; fi
  if vibe_has gh; then
    log_step "Checking for open PRs to main..."; open_prs=$(gh pr list --state open --base main --json number,headRefName,title | jq -r --arg b "$branch" '.[] | select(.headRefName != $b) | "#\(.number) \(.title) (\(.headRefName))"')
    [[ -n "$open_prs" ]] && { log_warn "Blocking: Sequential merge required. Other open PRs to 'main' detected."; echo "$open_prs" | sed 's/^/  - /'; return 1; }
  fi
  log_step "Bumping version ($bump_type) and updating CHANGELOG..."; ./scripts/bump.sh "$bump_type" "$version_msg" || return 1
  git add VERSION CHANGELOG.md 2>/dev/null || true; git commit -m "chore: bump version to $(cat VERSION)" 2>/dev/null || true
  log_step "Pushing changes to origin/$branch"; git push origin HEAD || return 1
  if ! vibe_has gh; then log_success "Changes pushed. Please create/view PR manually."; return 0; fi
  log_info "GitHub CLI detected. Managing PR..."
  if gh pr view "$branch" --json number >/dev/null 2>&1; then log_success "Updating existing PR..."; gh pr edit "$branch" --title "$pr_title" --body "$pr_body" || true
  else log_step "Creating new PR: $pr_title"; gh pr create --title "$pr_title" --body "$pr_body" --web || log_warn "Failed to create PR with gh, please check manually."
  fi
}

_flow_review() {
  local target="" pr_info number title state decision mergeable url comments retry=0 ci_status="PENDING" rollup_state="SUCCESS"
  while [[ $# -gt 0 ]]; do case "$1" in -h|--help) _flow_review_usage; return 0 ;; *) target="$1"; shift ;; esac; done
  vibe_require git || return 1; [[ -z "$target" ]] && target=$(git branch --show-current)
  if ! vibe_has gh; then log_warn "gh (GitHub CLI) not found. Falling back to local vibe check."; vibe check; return 0; fi
  log_step "Fetching PR status for '$target'..."; pr_info=$(gh pr view "$target" --json number,title,state,reviewDecision,mergeable,url,statusCheckRollup,comments 2>/dev/null)
  [[ $? -ne 0 ]] && { log_warn "No open PR found for '$target'. Running local health check..."; vibe check; return 0; }
  number=$(echo "$pr_info" | jq -r '.number'); title=$(echo "$pr_info" | jq -r '.title'); state=$(echo "$pr_info" | jq -r '.state')
  decision=$(echo "$pr_info" | jq -r '.reviewDecision // "PENDING"'); mergeable=$(echo "$pr_info" | jq -r '.mergeable'); url=$(echo "$pr_info" | jq -r '.url')
  echo "${BOLD}PR #$number:${NC} $title"; echo "${CYAN}URL:${NC} $url"; echo "${CYAN}State:${NC} $state | ${CYAN}Review:${NC} $decision | ${CYAN}Mergeable:${NC} $mergeable"
  log_step "Fetching latest review comments..."; comments=$(echo "$pr_info" | jq -r '.comments[-3:] | .[]? | "[\(.author.login)]: \(.body)"')
  [[ -n "$comments" ]] && echo "$comments" | sed 's/^/  💬 /' || echo "  (No comments found)"
  while [[ $retry -lt 3 ]]; do
    log_step "Checking CI status (Attempt $((retry+1))/3)..."
    ci_status=$(gh pr view "$target" --json statusCheckRollup -q '.statusCheckRollup[0].status // "SUCCESS"' 2>/dev/null || echo "SUCCESS")
    rollup_state=$(gh pr view "$target" --json statusCheckRollup -q '.statusCheckRollup[0].state // "SUCCESS"' 2>/dev/null); [[ -z "$rollup_state" || "$rollup_state" == "null" ]] && rollup_state="SUCCESS"
    if [[ "$rollup_state" == "PENDING" || "$ci_status" == "in_progress" || "$ci_status" == "queued" ]]; then log_info "CI is still running. Waiting 30s..."; sleep 30; retry=$((retry + 1))
    else PAGER=cat gh pr checks "$target" || true; break
    fi
  done
  [[ $retry -eq 3 ]] && log_warn "CI is taking too long. Please check manually using: ${CYAN}gh pr checks --watch${NC}"
  if [[ "$decision" == "APPROVED" && "$rollup_state" == "SUCCESS" ]]; then log_success "Ready to merge! All criteria met."
  elif [[ "$decision" == "CHANGES_REQUESTED" ]]; then log_error "Changes requested. Please address review comments."
  elif [[ "$state" == "MERGED" ]]; then log_success "PR already merged. Time to run 'vibe flow done'."
  else log_info "PR is currently active. Target: Approval + CI Success."
  fi
}

vibe_flow() {
  case "${1:-help}" in
    start|new|create) shift; _flow_new "$@" ;;
    done) shift; _flow_done "$@" ;;
    status) shift; _flow_status "$@" ;;
    list) shift; _flow_list "$@" ;;
    sync) _flow_sync ;;
    pr) shift; _flow_pr "$@" ;;
    review) shift; _flow_review "$@" ;;
    *) _flow_usage ;;
  esac
}
