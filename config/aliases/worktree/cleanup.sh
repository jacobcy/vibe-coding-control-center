#!/usr/bin/env zsh
# Worktree cleanup operations
# Part of V3 Execution Plane

# Remove worktree(s): wtrm <name|path|all>
# V3: Enhanced with confirmation prompts
wtrm() {
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }
  local arg="$1" force="$2"
  [[ -z "$arg" ]] && vibe_die "usage: wtrm <wt-dir|path|all> [--force]"

  local main_dir; main_dir="$($git_cmd rev-parse --show-toplevel 2>/dev/null)" || { vibe_die "Not in git repo"; return 1; }

  _wtrm_one() {
    local p="$1" label="${1##*/}"
    [[ "$p" == "$main_dir" ]] && { echo "⚠️  Cannot remove main worktree"; return 1; }

    # V3: Confirmation prompt (unless --force)
    if [[ "$force" != "--force" ]]; then
      echo -n "❓ Remove worktree '$label'? [y/N] "
      local response
      read -r response
      [[ ! "$response" =~ ^[yY]$ ]] && { echo "ℹ️  Skipped: $label"; return 0; }
    fi

    local branch_name=""
    if [[ -d "$p" ]]; then
      branch_name=$($git_cmd -C "$p" rev-parse --abbrev-ref HEAD 2>/dev/null)
    fi
    if [[ -z "$branch_name" ]]; then
      branch_name=$($git_cmd -C "$main_dir" worktree list --porcelain | awk -v path="$p" '
        /^worktree / { if ($2 == path) found=1; else found=0 }
        /^branch / && found { sub("refs/heads/", "", $2); print $2; exit }
      ')
    fi

    if $git_cmd -C "$main_dir" worktree remove --force "$p" 2>/dev/null; then
      echo "✅ Removed: $label"

      if [[ -n "$branch_name" && "$branch_name" != "main" && "$branch_name" != "master" ]]; then
        if $git_cmd -C "$main_dir" branch -D "$branch_name" >/dev/null 2>&1; then
           echo "🗑️  Deleted local branch: $branch_name"
        fi
        if $git_cmd -C "$main_dir" ls-remote --exit-code --heads origin "$branch_name" >/dev/null 2>&1; then
           echo -n "❓ Delete remote branch origin/$branch_name? [y/N] "
           local response
           read -r response
           if [[ "$response" =~ ^[yY]$ ]]; then
              if $git_cmd -C "$main_dir" push origin --delete "$branch_name"; then
                 echo "🗑️  Deleted remote branch: origin/$branch_name"
              fi
           else
              echo "ℹ️  Kept remote branch"
           fi
        fi
      fi
    elif [[ -d "$p" ]]; then
      command rm -rf "$p"; echo "🗑️  Deleted orphan: $label"
    else
      echo "⚠️  Not found: $p"
    fi
  }

  if [[ "$arg" == "all" ]]; then
    local -a paths=()
    while IFS= read -r wp; do
      [[ "$wp" == "$main_dir" ]] && continue
      [[ "${wp##*/}" == wt-* ]] && paths+=("$wp")
    done < <($git_cmd -C "$main_dir" worktree list --porcelain | awk '/^worktree /{print $2}')
    [[ ${#paths[@]} -eq 0 ]] && { echo "ℹ️  No wt-* worktrees"; return 0; }
    echo "🗑️  Found ${#paths[@]} worktree(s)..."
    for wp in "${paths[@]}"; do _wtrm_one "$wp"; done
  else
    local path
    [[ "$arg" == /* ]] && path="$arg" || path="${main_dir:h}/$arg"
    [[ "$path" =~ /wt- ]] || { echo "⚠️  Name must contain 'wt-': $arg"; return 1; }
    _wtrm_one "$path"
  fi
  $git_cmd -C "$main_dir" worktree prune >/dev/null 2>&1 || true
}
