#!/usr/bin/env zsh

_vibe_check_link_runtime_worktree_errors() {
  local registry_file="$1" wt_names_json="$2" errors_ref="$3"
  local line

  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    typeset -g "$errors_ref"="${(P)errors_ref}runtime points to missing worktree: $line\n"
  done < <(jq -r --argjson wt_names "$wt_names_json" '
    .tasks[]?
    | (.runtime_worktree_name // "") as $wt
    | select($wt != "")
    | select($wt_names | index($wt) | not)
    | "\(.task_id):\($wt)"
  ' "$registry_file" 2>/dev/null)
}
