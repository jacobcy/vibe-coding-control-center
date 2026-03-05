#!/usr/bin/env zsh

_vibe_task_update() {
    local task_id="${1:-}" task_status="" agent="" worktree="" branch="" next_step="" bind_current="false" force=0 common_dir registry_file worktrees_file now target_name="" target_path="" email_slug="" unassign="false"
    shift $(( $# > 0 ? 1 : 0 ))
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { _vibe_task_usage; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for update"; return 1; }
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status|--agent|--worktree|--branch|--next-step) [[ $# -ge 2 ]] || { vibe_die "Missing value for $1"; return 1; }; case "$1" in --status) task_status="$2" ;; --agent) agent="$2" ;; --worktree) worktree="$2" ;; --branch) branch="$2" ;; --next-step) next_step="$2" ;; esac; shift 2 ;;
            --bind-current) bind_current="true"; shift ;;
            --unassign) unassign="true"; shift ;;
            -f|--force) force=1; shift ;;
            -h|--help) _vibe_task_usage; return 0 ;;
            *) vibe_die "Unknown update option: $1"; return 1 ;;
        esac
    done
    [[ -n "$task_status$agent$worktree$branch$next_step" || "$bind_current" == "true" || "$unassign" == "true" ]] || { vibe_die "No update fields provided"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    if [[ -n "$agent" ]]; then
        case "$agent" in codex|antigravity|trae|claude|opencode|kiro) ;; *) [[ "$force" -eq 1 ]] || { vibe_die "Unsupported agent: $agent"; return 1; } ;; esac
        email_slug="$agent"; [[ "$force" -eq 1 ]] && email_slug="$(_vibe_task_slugify "$agent")"
        git config user.name "$agent" 2>/dev/null || git config user.name "$agent" || return 1
        git config user.email "${email_slug}@vibe.coding" 2>/dev/null || git config user.email "${email_slug}@vibe.coding" || return 1
    fi
    [[ "$unassign" == "true" ]] && worktree=""
    [[ "$bind_current" == "true" ]] && { target_name="$(basename "$PWD")"; target_path="$PWD"; worktree="$target_name"; }
    [[ -z "$target_name" ]] && target_name="$worktree"
    _vibe_task_write_registry "$registry_file" "$task_id" "$task_status" "$next_step" "$worktree" "$agent" "$now" || return 1
    _vibe_task_write_task_file "$common_dir" "$registry_file" "$task_id" "$now" || return 1
    _vibe_task_write_worktrees "$worktrees_file" "$target_name" "$target_path" "$task_id" "$branch" "$agent" "$bind_current" "$now" "$unassign" || return 1
    [[ "$bind_current" == "true" ]] && _vibe_task_refresh_cache "$common_dir" "$registry_file" "$task_id" "$target_name" "$now"
    case "$task_status" in
        todo) echo "💡 Next: Create a worktree using ${CYAN}wtnew <branch>${NC} or start with ${CYAN}vnew <branch>${NC}" ;;
        in_progress) echo "💡 Next: Ensure your cockpit is ready with ${CYAN}vup${NC}" ;;
        done|merged) echo "💡 Next: Cleanup with ${CYAN}vibe flow done${NC} or remove with ${CYAN}vibe task remove${NC}" ;;
    esac
    return 0
}
_vibe_task_add() {
    local task_id="" title="" common_dir registry_file task_file now tmp
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then echo "Usage: vibe task add <title> [--id <task-id>]"; return 0; fi
    if [[ $# -gt 0 && ! "$1" =~ ^-- ]]; then title="$1"; shift; fi
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title) title="$2"; shift 2 ;;
            --id) task_id="$2"; shift 2 ;;
            *) vibe_die "Unknown add option: $1"; return 1 ;;
        esac
    done
    [[ -n "$title" ]] || { vibe_die "Missing title/feature name for task add"; return 1; }
    if [[ -z "$task_id" ]]; then local slug; slug="$(_vibe_task_slugify "$title")"; task_id="$(_vibe_task_today)-$slug"; fi
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 && { vibe_die "Task already exists: $task_id"; return 1; }
    mkdir -p "$(dirname "$task_file")"; tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg title "$title" --arg now "$now" '.tasks += [{task_id:$task_id,title:$title,status:"todo",current_subtask_id:null,assigned_worktree:null,next_step:"",updated_at:$now}]' "$registry_file" > "$tmp" && mv "$tmp" "$registry_file" || return 1
    jq -n --arg task_id "$task_id" --arg title "$title" '{task_id:$task_id,title:$title,status:"todo",subtasks:[],assigned_worktree:null,next_step:""}' > "$task_file"
    log_success "Task added: $task_id"
    echo "💡 Next: Run ${CYAN}wtnew <branch>${NC} or ${CYAN}vnew <branch>${NC} to start development."
}
_vibe_task_branch_matches_any() { local branch="$1" candidate; shift; for candidate in "$@"; do [[ -n "$candidate" && ( "$branch" == "$candidate" || "$branch" == */"$candidate" ) ]] && return 0; done; return 1; }
_vibe_task_remove() {
    local task_id="${1:-}" common_dir registry_file worktrees_file task_file tmp
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { echo "Usage: vibe task remove <task-id>"; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for remove"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    jq -e --arg task_id "$task_id" '.worktrees[]? | select(.current_task == $task_id or (.tasks // [] | index($task_id) != null))' "$worktrees_file" >/dev/null 2>&1 && { vibe_die "Task is still bound to a worktree: $task_id"; return 1; }
    local indexed_branch task_title="" task_suffix="" task_slug="" local_branches="" remote_branches="" residual_local="" residual_remote=""
    local -a branch_candidates local_matches remote_matches
    indexed_branch=$(jq -r --arg tid "$task_id" '.worktrees[]? | select(.current_task == $tid or (.tasks // [] | index($tid) != null)) | .branch // empty' "$worktrees_file" | head -1)
    task_title=$(jq -r --arg tid "$task_id" '.tasks[]? | select(.task_id == $tid) | .title // empty' "$registry_file" | head -1)
    [[ -n "$task_title" ]] && task_slug="$(_vibe_task_slugify "$task_title")"
    [[ "$task_id" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-(.+)$ ]] && task_suffix="${match[1]}"
    [[ -n "$indexed_branch" ]] && branch_candidates+=("$indexed_branch")
    branch_candidates+=("$task_id")
    [[ -n "$task_suffix" ]] && branch_candidates+=("$task_suffix")
    [[ -n "$task_slug" ]] && branch_candidates+=("$task_slug")
    while read -r lb; do [[ -n "$lb" ]] && _vibe_task_branch_matches_any "$lb" "${branch_candidates[@]}" && local_matches+=("$lb"); done < <(git for-each-ref --format='%(refname:short)' refs/heads 2>/dev/null)
    while read -r rb; do [[ -n "$rb" && "$rb" != "origin/HEAD" ]] && _vibe_task_branch_matches_any "$rb" "${branch_candidates[@]}" && remote_matches+=("$rb"); done < <(git for-each-ref --format='%(refname:short)' refs/remotes/origin 2>/dev/null)
    (( ${#local_matches[@]} > 0 )) && local_branches="$(printf '%s\n' "${local_matches[@]}" | sort -u | sed '/^$/d')"
    (( ${#remote_matches[@]} > 0 )) && remote_branches="$(printf '%s\n' "${remote_matches[@]}" | sort -u | sed '/^$/d')"
    if [[ -n "$local_branches" || -n "$remote_branches" ]]; then
        log_warn "Branch(es) detected for this task:"
        [[ -n "$local_branches" ]] && echo "$local_branches" | sed 's/^/  - local: /'
        [[ -n "$remote_branches" ]] && echo "$remote_branches" | sed 's/^/  - remote: /'
        if confirm_action "Delete these branches before removing task?"; then
            while read -r lb; do [[ -n "$lb" ]] && vibe_delete_local_branch "$lb" || residual_local+="$lb\n"; done <<< "$local_branches"
            while read -r rb; do
                [[ -z "$rb" ]] && continue
                local rb_name="${rb#origin/}"
                vibe_delete_remote_branch "$rb_name" || residual_remote+="$rb_name\n"
            done <<< "$remote_branches"
        else
            vibe_die "Task removal cancelled: branch cleanup is required."
            return 1
        fi
        if [[ -n "$residual_local" || -n "$residual_remote" ]]; then
            log_warn "Branch residue detected for task $task_id:"
            [[ -n "$residual_local" ]] && echo "$residual_local" | sed '/^$/d; s/^/  - local: /'
            [[ -n "$residual_remote" ]] && echo "$residual_remote" | sed '/^$/d; s/^/  - remote: /'
            vibe_die "Task removal blocked: unable to delete all related branches."
            return 1
        fi
    fi
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" '.tasks |= map(select(.task_id != $task_id))' "$registry_file" > "$tmp" && mv "$tmp" "$registry_file" || return 1
    rm -f "$task_file"; rmdir "$(dirname "$task_file")" 2>/dev/null || true; log_success "Task $task_id removed from registry."
}
_vibe_task_sync() {
    local common_dir registry_file repo_root openspec_tasks_file task_json
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
    openspec_tasks_file="$(mktemp)" || return 1; _vibe_task_collect_openspec_tasks "$repo_root" > "$openspec_tasks_file"
    local tasks_list; tasks_list=$(jq -c '.tasks[]?' "$openspec_tasks_file" 2>/dev/null)
    if [[ -n "$tasks_list" ]]; then
        while read -r task_json; do
            [[ -n "$task_json" ]] || continue; local tid; tid=$(echo "$task_json" | jq -r '.task_id // empty'); [[ -n "$tid" ]] || continue
            local title; title=$(echo "$task_json" | jq -r '.title // "OpenSpec Task"')
            local t_status; t_status=$(echo "$task_json" | jq -r '.status // "todo"')
            local next; next=$(echo "$task_json" | jq -r '.next_step // ""')
            if ! jq -e --arg tid "$tid" '.tasks[]? | select(.task_id == $tid)' "$registry_file" >/dev/null 2>&1; then
                local tmp_add; tmp_add="$(mktemp)"
                jq --arg tid "$tid" --arg title "$title" --arg status "$t_status" --arg next "$next" --arg now "$now" \
                   '.tasks += [{task_id:$tid, title:$title, status:$status, next_step:$next, updated_at:$now}]' \
                   "$registry_file" > "$tmp_add" && mv "$tmp_add" "$registry_file"
            fi
            log_step "Syncing OpenSpec task: $tid"; _vibe_task_update "$tid" --status "$t_status" --next-step "$next" >/dev/null
            local tmp; tmp="$(mktemp)"
            jq --arg tid "$tid" --arg title "$title" --arg src "openspec/changes/$tid" \
               '.tasks |= map(if .task_id == $tid then .title = $title | .framework = "openspec" | .source_path = $src else . end)' \
               "$registry_file" > "$tmp" && mv "$tmp" "$registry_file"
        done <<< "$tasks_list"
    fi
    rm -f "$openspec_tasks_file"; log_success "OpenSpec tasks synced to registry."
}
