#!/usr/bin/env zsh

_flow_pr_bound_spec_ref() {
  local flow_record current_task spec_ref
  flow_record="$(_flow_show --json 2>/dev/null || true)"
  [[ -n "$flow_record" ]] || return 0

  current_task="$(print -r -- "$flow_record" | jq -r '.current_task // empty' 2>/dev/null)"
  [[ -n "$current_task" ]] || return 0

  spec_ref="$(print -r -- "$flow_record" | jq -r '.spec_ref // empty' 2>/dev/null)"
  if [[ -z "$spec_ref" ]]; then
    log_error "Current task '$current_task' is missing spec_ref. Bind a plan before vibe flow pr."
    return 1
  fi
  [[ -f "$spec_ref" ]] || {
    log_error "Bound plan file not found for task '$current_task': $spec_ref"
    return 1
  }
  print -r -- "$spec_ref"
}

_flow_pr_stage_managed_files() {
  local file
  (( $# > 0 )) || return 0
  for file in "$@"; do
    git add -- "$file" 2>/dev/null || {
      log_error "Failed to stage managed PR artifact: $file"
      return 1
    }
    log_info "Ensured managed PR artifact is staged: $file"
  done
}

_flow_pr_commit_managed_files() {
  local commit_msg="$1"
  shift
  (( $# > 0 )) || return 0
  git diff --quiet HEAD -- "$@" 2>/dev/null && return 0
  git commit --only -m "$commit_msg" -- "$@" 2>/dev/null || {
    log_error "Failed to create managed artifact commit."
    return 1
  }
}

_flow_pr_changelog_cache_dir() {
  local dir
  dir="$(git rev-parse --git-common-dir)/vibe/changelog-msg" || return 1
  mkdir -p "$dir" || return 1
  print -r -- "$dir"
}

_flow_pr_changelog_cache_key() {
  local branch="$1"
  print -r -- "${branch//[^A-Za-z0-9._-]/_}"
}

_flow_pr_changelog_cache_file() {
  local branch="$1" cache_dir cache_key
  cache_dir="$(_flow_pr_changelog_cache_dir)" || return 1
  cache_key="$(_flow_pr_changelog_cache_key "$branch")"
  print -r -- "$cache_dir/$cache_key.txt"
}

_flow_pr_validate_changelog_message() {
  local raw_msg="$1" trimmed_msg
  trimmed_msg="${raw_msg#"${raw_msg%%[![:space:]]*}"}"
  trimmed_msg="${trimmed_msg%"${trimmed_msg##*[![:space:]]}"}"
  [[ -n "$trimmed_msg" ]] || {
    log_error "Invalid changelog message: empty value is not allowed."
    return 1
  }
  case "$trimmed_msg" in
    "..."|"Automated version bump and updates.")
      log_error "Invalid changelog message: placeholder text is not allowed."
      return 1
      ;;
  esac
  print -r -- "$trimmed_msg"
}

_flow_pr_read_cached_changelog_message() {
  local branch="$1" cache_file
  cache_file="$(_flow_pr_changelog_cache_file "$branch")" || return 1
  [[ -f "$cache_file" ]] || return 1
  cat "$cache_file"
}

_flow_pr_write_cached_changelog_message() {
  local branch="$1" changelog_msg="$2" cache_file
  cache_file="$(_flow_pr_changelog_cache_file "$branch")" || return 1
  print -r -- "$changelog_msg" > "$cache_file" || {
    log_error "Failed to write changelog message cache for branch '$branch'."
    return 1
  }
}

_flow_pr() {
  local bump_type="" pr_title="" pr_body="" version_msg="" branch base_name="" base_git_ref="" commit_logs open_prs use_web=0 spec_ref="" explicit_version_msg="" cached_version_msg="" validated_msg=""
  local -a managed_files
  while [[ $# -gt 0 ]]; do case "$1" in -h|--help) _flow_pr_usage; return 0 ;; --base) base_name="$2"; shift 2 ;; --bump) bump_type="$2"; shift 2 ;; --title) pr_title="$2"; shift 2 ;; --body) pr_body="$2"; shift 2 ;; --msg) version_msg="$2"; shift 2 ;; --web) use_web=1; shift ;; *) shift ;; esac; done
  vibe_require git || return 1; branch=$(git branch --show-current); [[ "$branch" == "main" ]] && { log_error "Cannot create PR from main branch"; return 1; }
  explicit_version_msg="$version_msg"
  spec_ref="$(_flow_pr_bound_spec_ref)" || return 1
  [[ -n "$spec_ref" ]] && managed_files+=("$spec_ref")
  base_name="$(_flow_resolve_pr_base "$base_name" "$branch")" || return 1
  base_git_ref="$(_flow_pr_base_git_ref "$base_name")" || return 1
  if vibe_has gh; then
    _flow_require_base_ref "$base_name" || return 1
  fi
  _flow_require_latest_pr_base "$base_name" "$base_git_ref" || return 1
  log_info "Using PR base: $base_name"
  commit_logs=$(git log "$base_git_ref..HEAD" --oneline); [[ -z "$commit_logs" ]] && { log_warn "No new commits since $base_name. Nothing to PR."; return 1; }
  [[ -z "$bump_type" ]] && bump_type="patch"; [[ -z "$pr_title" ]] && pr_title=$(echo "$commit_logs" | head -n 1 | sed 's/^[a-f0-9]* //'); [[ -z "$pr_body" ]] && pr_body=$(echo "$commit_logs" | sed 's/^[a-f0-9]* / - /')
  
  # Auto-link issues
  local flow_record issue_refs fixes_block=""
  flow_record=$(_flow_show --json 2>/dev/null)
  if [[ -n "$flow_record" ]]; then
    issue_refs=$(print -r -- "$flow_record" | jq -r '(.issue_refs // []) | .[]' | grep '^gh-' | sed 's/^gh-//' || true)
    if [[ -n "$issue_refs" ]]; then
      while read -r issue_num; do
        [[ -n "$issue_num" ]] && fixes_block+="\nFixes #$issue_num"
      done <<< "$issue_refs"
      if [[ -n "$fixes_block" ]]; then
        pr_body+="\n\n## Linked Issues${fixes_block}"
      fi
    fi
  fi

  if [[ -n "$explicit_version_msg" ]]; then
    validated_msg="$(_flow_pr_validate_changelog_message "$explicit_version_msg")" || return 1
    version_msg="$validated_msg"
    _flow_pr_write_cached_changelog_message "$branch" "$version_msg" || return 1
  else
    cached_version_msg="$(_flow_pr_read_cached_changelog_message "$branch" 2>/dev/null || true)"
    if [[ -n "$cached_version_msg" ]]; then
      validated_msg="$(_flow_pr_validate_changelog_message "$cached_version_msg")" || return 1
      version_msg="$validated_msg"
      log_info "Reusing cached changelog message for branch '$branch'."
    fi
  fi

  local has_pr=0
  if vibe_has gh; then
    log_step "Checking for open PRs to $base_name..."; open_prs=$(gh pr list --state open --base "$base_name" --json number,headRefName,title | jq -r --arg b "$branch" '.[] | select(.headRefName != $b) | "#\(.number) \(.title) (\(.headRefName))"')
    [[ -n "$open_prs" ]] && { log_warn "Blocking: Sequential merge required. Other open PRs to '$base_name' detected."; echo "$open_prs" | sed 's/^/  - /'; return 1; }

    gh pr view "$branch" >/dev/null 2>&1 && has_pr=1
  fi

  local skip_bump=0
  [[ $has_pr -eq 1 ]] && skip_bump=1
  [[ -n "$version_msg" && -f CHANGELOG.md ]] && grep -qF "$version_msg" CHANGELOG.md 2>/dev/null && skip_bump=1

  if [[ $skip_bump -eq 0 && -z "$version_msg" ]]; then
    log_error "Missing changelog message. First publish on this branch must provide --msg with a non-placeholder release note."
    return 1
  fi

  if [[ $skip_bump -eq 0 ]]; then
    log_step "Bumping version ($bump_type) and updating CHANGELOG..."; ./scripts/bump.sh "$bump_type" "$version_msg" || return 1
    managed_files+=("VERSION" "CHANGELOG.md")
    _flow_pr_stage_managed_files "${managed_files[@]}" || return 1
    _flow_pr_commit_managed_files "chore: bump version to $(cat VERSION)" "${managed_files[@]}" || return 1
  else
    log_info "Skipping version bump (PR exists or changelog already up-to-date)."
    _flow_pr_stage_managed_files "${managed_files[@]}" || return 1
    _flow_pr_commit_managed_files "chore: update managed pr artifacts" "${managed_files[@]}" || return 1
  fi

  log_step "Pushing changes to origin/$branch"; git push origin HEAD || return 1
  if ! vibe_has gh; then log_success "Changes pushed. Please create/view PR manually."; return 0; fi
  log_info "GitHub CLI detected. Managing PR..."
  if [[ $has_pr -eq 1 ]]; then
    log_success "Updating existing PR..."
    gh pr edit "$branch" --base "$base_name" --title "$pr_title" --body "$pr_body" || true
  else
    log_step "Creating new PR: $pr_title"
    if [[ $use_web -eq 1 ]]; then
      gh pr create --title "$pr_title" --body "$pr_body" --base "$base_name" --web || log_warn "Failed to create PR with gh, please check manually."
    else
      gh pr create --title "$pr_title" --body "$pr_body" --base "$base_name" || log_warn "Failed to create PR with gh, please check manually."
    fi
  fi
}
