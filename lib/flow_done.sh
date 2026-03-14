#!/usr/bin/env zsh

# Flow done closeout functions
# Handles PR merge, branch cleanup, and worktree state management

_flow_done() {
  local target_branch="" arg unmerged current_branch branch_ref="" branch_name feature_slug flow_record="" tasks_json='[]' current_task="" worktree_name="" worktree_path="" pr_ref="" now pr_merged=1 delete_mode="safe"
  for arg in "$@"; do 
    [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_done_usage; return 0; }
  done
  while [[ $# -gt 0 ]]; do 
    case "$1" in 
      --branch) target_branch="$2"; shift 2 ;;
      -*) log_error "Unknown option: $1"; _flow_done_usage; return 1 ;;
      *) shift ;;
    esac
  done
  current_branch=$(git branch --show-current)
  if _flow_is_main_worktree; then
    log_warn "Current repository or branch is protected."
    return 1
  fi
  if [[ -z "$target_branch" ]]; then
    target_branch="$current_branch"
  fi
  if [[ "$target_branch" == "main" ]]; then
    log_error "Cannot close main branch flow."
    return 1
  fi
  
  branch_ref="$(_flow_branch_ref "$target_branch")" || {
    log_error "Branch not found: $target_branch"
    return 1
  }
  branch_name="${branch_ref#origin/}"
  feature_slug="$(_flow_feature_slug "$branch_name")"
  _flow_history_has_closed_feature "$feature_slug" && { log_error "Flow already closed: $feature_slug"; return 1; }
  _flow_branch_has_pr "$branch_name" || { log_error "Branch '$target_branch' has no PR history. Use skill handoff instead of force-closing."; return 1; }

  # 如果检查的是当前分支，额外检查工作目录
  if [[ "$branch_ref" == "$current_branch" ]]; then
    if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
      log_error "Working directory is not clean. Please commit or stash changes before finishing."
      return 1
    fi
  fi
  # 获取远程 main 分支最新状态
  git fetch origin main --quiet 2>/dev/null || true
  unmerged=$(git rev-list "origin/main..$branch_ref" 2>/dev/null || echo "")

  if _flow_branch_pr_merged "$branch_name"; then
    pr_merged=0
    delete_mode="force"
  elif [[ -z "$unmerged" ]]; then
    pr_merged=0
  else
    _flow_review_has_evidence "$branch_name" || {
      log_error "Branch '$target_branch' has no review evidence. Wait for Copilot/Codex review, or post a local review comment from 'vibe flow review --local' before done."
      return 1
    }
    vibe_has gh || {
      log_error "gh (GitHub CLI) is required to merge reviewed PRs during vibe flow done."
      return 1
    }

    # Check for unmet PR dependencies before merge
    local pr_number unmet_deps
    pr_number=$(gh pr view "$branch_name" --json number --jq '.number' 2>/dev/null || true)
    if [[ -n "$pr_number" ]]; then
      local common_dir
      common_dir="$(vibe_git_dir)" || return 1
      unmet_deps="$(_vibe_roadmap_pr_check_unmet_dependencies "$common_dir" "$pr_number")"

      if [[ "$(echo "$unmet_deps" | jq 'length')" -gt 0 ]]; then
        log_warn "PR #$pr_number has unmet merge dependencies:"
        echo "$unmet_deps" | jq -r '.[]' | while read -r dep; do
          echo "  - PR #$dep must be merged first"
        done
        echo ""
        log_warn "Proceeding with merge may violate the intended merge order."

        # In non-interactive mode, fail. In interactive mode, prompt user.
        if [[ -t 0 ]]; then
          read -k 1 "?Continue anyway? [y/N] " || { echo ""; return 1; }
          echo ""
          [[ "$REPLY" =~ ^[Yy]$ ]] || { log_error "Merge cancelled"; return 1; }
        else
          log_error "Unmet dependencies detected. Resolve dependencies first or run in interactive mode."
          return 1
        fi
      fi
    fi

    log_step "Review evidence found. Merging PR for branch: $branch_name"
    gh pr merge "$branch_name" --merge || {
      log_error "Failed to merge PR for branch '$branch_name'. Resolve merge blockers, then re-run vibe flow done."
      return 1
    }
    if _flow_branch_pr_merged "$branch_name"; then
      pr_merged=0
      delete_mode="force"
    fi
  fi

  # 无法确认 PR merged 时，回退到 Git 提交检查
  if [[ $pr_merged -ne 0 && -n "$unmerged" ]]; then
    log_error "Branch '$target_branch' has commits not merged into origin/main. Please open a PR and merge first."
    return 1
  fi

  flow_record="$(_flow_branch_dashboard_entry "$branch_name")"
  local flow_record_status=$?
  if [[ "$flow_record_status" -ne 0 && "$flow_record_status" -ne 1 ]]; then
    return "$flow_record_status"
  fi
  if [[ -n "$flow_record" ]]; then
    tasks_json="$(echo "$flow_record" | jq -c '.tasks // []')"
    current_task="$(echo "$flow_record" | jq -r '.current_task // empty')"
    worktree_name="$(echo "$flow_record" | jq -r '.worktree_name // empty')"
    worktree_path="$(echo "$flow_record" | jq -r '.worktree_path // empty')"
    pr_ref="$(echo "$flow_record" | jq -r '.pr_ref // empty')"
  fi
  now="$(_flow_now_iso)"
  _flow_history_close "$feature_slug" "$branch_name" "$worktree_name" "$worktree_path" "$current_task" "$tasks_json" "$pr_ref" "$now" || return 1
  _flow_close_branch_runtime "$branch_name" || return 1
  _flow_close_branch_tasks "$branch_name" || return 1

  if [[ "$branch_name" == "$current_branch" ]]; then
    _flow_checkout_safe_main_branch || { log_error "Failed to move current worktree onto a safe branch after closeout: $branch_name"; return 1; }
  fi

  # Check if branch is occupied by another worktree before deletion
  if vibe_is_branch_occupied_by_worktree "$branch_name"; then
    log_warn "Branch '$branch_name' is checked out in another worktree. Skipping local branch deletion."
    log_info "The branch will remain until all worktrees using it are removed."
  elif git show-ref --verify --quiet "refs/heads/$branch_name"; then
    vibe_delete_local_branch "$branch_name" "$delete_mode" || return 1
  fi
  if git show-ref --verify --quiet "refs/remotes/origin/$branch_name"; then
    vibe_delete_remote_branch "$branch_name" || return 1
  fi

  log_success "Flow closed for branch '$branch_name'. History preserved."
  echo "💡 Next: Run ${CYAN}vibe flow show $feature_slug${NC} or your closing skill to finish task/issue handoff."
}

