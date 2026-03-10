#!/usr/bin/env zsh

_flow_pr() {
  local bump_type="" pr_title="" pr_body="" version_msg="" branch base_name="" base_git_ref="" commit_logs first_msg open_prs
  while [[ $# -gt 0 ]]; do case "$1" in -h|--help) _flow_pr_usage; return 0 ;; --base) base_name="$2"; shift 2 ;; --bump) bump_type="$2"; shift 2 ;; --title) pr_title="$2"; shift 2 ;; --body) pr_body="$2"; shift 2 ;; --msg) version_msg="$2"; shift 2 ;; *) shift ;; esac; done
  vibe_require git || return 1; branch=$(git branch --show-current); [[ "$branch" == "main" ]] && { log_error "Cannot create PR from main branch"; return 1; }
  base_name="$(_flow_resolve_pr_base "$base_name" "$branch")" || return 1
  base_git_ref="$(_flow_pr_base_git_ref "$base_name")" || return 1
  if vibe_has gh; then
    _flow_require_base_ref "$base_name" || return 1
  fi
  log_info "Using PR base: $base_name"
  commit_logs=$(git log "$base_git_ref..HEAD" --oneline); [[ -z "$commit_logs" ]] && { log_warn "No new commits since $base_name. Nothing to PR."; return 1; }
  [[ -z "$bump_type" ]] && bump_type="patch"; [[ -z "$pr_title" ]] && pr_title=$(echo "$commit_logs" | head -n 1 | sed 's/^[a-f0-9]* //'); [[ -z "$pr_body" ]] && pr_body=$(echo "$commit_logs" | sed 's/^[a-f0-9]* / - /')
  if [[ -z "$version_msg" ]]; then first_msg=$(echo "$commit_logs" | tail -n 1 | sed 's/^[a-f0-9]* //'); version_msg="${first_msg} ..."; fi

  local has_pr=0
  if vibe_has gh; then
    log_step "Checking for open PRs to $base_name..."; open_prs=$(gh pr list --state open --base "$base_name" --json number,headRefName,title | jq -r --arg b "$branch" '.[] | select(.headRefName != $b) | "#\(.number) \(.title) (\(.headRefName))"')
    [[ -n "$open_prs" ]] && { log_warn "Blocking: Sequential merge required. Other open PRs to '$base_name' detected."; echo "$open_prs" | sed 's/^/  - /'; return 1; }

    gh pr view "$branch" >/dev/null 2>&1 && has_pr=1
  fi

  local skip_bump=0
  [[ $has_pr -eq 1 ]] && skip_bump=1
  [[ -f CHANGELOG.md ]] && grep -qF "$version_msg" CHANGELOG.md 2>/dev/null && skip_bump=1

  if [[ $skip_bump -eq 0 ]]; then
    log_step "Bumping version ($bump_type) and updating CHANGELOG..."; ./scripts/bump.sh "$bump_type" "$version_msg" || return 1
    git add VERSION CHANGELOG.md 2>/dev/null || true; git commit -m "chore: bump version to $(cat VERSION)" 2>/dev/null || true
  else
    log_info "Skipping version bump (PR exists or changelog already up-to-date)."
  fi

  log_step "Pushing changes to origin/$branch"; git push origin HEAD || return 1
  if ! vibe_has gh; then log_success "Changes pushed. Please create/view PR manually."; return 0; fi
  log_info "GitHub CLI detected. Managing PR..."
  if [[ $has_pr -eq 1 ]]; then
    log_success "Updating existing PR..."
    gh pr edit "$branch" --base "$base_name" --title "$pr_title" --body "$pr_body" || true
  else
    log_step "Creating new PR: $pr_title"
    gh pr create --title "$pr_title" --body "$pr_body" --base "$base_name" --web || log_warn "Failed to create PR with gh, please check manually."
  fi
}