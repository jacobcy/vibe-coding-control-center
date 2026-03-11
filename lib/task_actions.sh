#!/usr/bin/env zsh
_vibe_task_roadmap_file() {
    echo "$1/vibe/roadmap.json"
}
_vibe_task_validate_roadmap_items() {
    local common_dir="$1" roadmap_item_ids_json="$2" roadmap_file missing_ids first_missing
    [[ "${roadmap_item_ids_json:-[]}" == "[]" ]] && return 0
    roadmap_file="$(_vibe_task_roadmap_file "$common_dir")"
    [[ -f "$roadmap_file" ]] || { vibe_die "Missing roadmap.json: $roadmap_file"; return 1; }
    jq empty "$roadmap_file" >/dev/null 2>&1 || { vibe_die "Invalid roadmap.json: $roadmap_file"; return 1; }
    missing_ids="$(jq -nr --argjson roadmap_item_ids "$roadmap_item_ids_json" --slurpfile roadmap "$roadmap_file" '
      ($roadmap[0].items // [] | map(.roadmap_item_id)) as $existing
      | $roadmap_item_ids[]
      | . as $target
      | select($existing | index($target) | not)
    ')" || { vibe_die "Invalid roadmap.json: $roadmap_file"; return 1; }

    if [[ -n "$missing_ids" ]]; then
        first_missing="$(printf '%s\n' "$missing_ids" | sed -n '1p')"
        vibe_die "Roadmap item not found: $first_missing"
        return 1
    fi
}
_vibe_task_sync_roadmap_links() {
    local common_dir="$1" task_id="$2" roadmap_item_ids_json="$3" now="$4" roadmap_file tmp
    [[ "${roadmap_item_ids_json:-[]}" == "[]" ]] && return 0
    roadmap_file="$(_vibe_task_roadmap_file "$common_dir")"
    [[ -f "$roadmap_file" ]] || { vibe_die "Missing roadmap.json: $roadmap_file"; return 1; }
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg now "$now" --argjson roadmap_item_ids "$roadmap_item_ids_json" '
      .items |= map(
        . as $item
        | if ($roadmap_item_ids | index($item.roadmap_item_id)) != null then
          .linked_task_ids = (((.linked_task_ids // []) + [$task_id]) | unique)
          | .updated_at = $now
        else . end
      )
    ' "$roadmap_file" > "$tmp" && mv "$tmp" "$roadmap_file"
}
_vibe_task_require_plan_binding_for_add() {
    local spec_standard="$1" spec_ref="$2"
    if [[ "$spec_standard" == "none" || -z "$spec_ref" ]]; then
        vibe_die "Task creation requires a plan binding. Create or select a roadmap item via 'vibe roadmap add (shell)', then use the writing-plans skill to produce a plan, and re-run vibe task add with --spec-standard/--spec-ref."
        return 1
    fi
}
_vibe_task_update() {
    local task_id="${1:-}" task_status="" agent="" worktree="" branch="" next_step="" bind_current="false" force=0 common_dir registry_file worktrees_file now target_name="" target_path="" email_slug="" unassign="false" assigned_mode="preserve" pr_ref="" pr_mode="preserve" issue_mode="preserve" roadmap_mode="preserve" spec_standard="" spec_ref="" spec_mode="preserve"
    local -a issue_refs roadmap_item_ids
    shift $(( $# > 0 ? 1 : 0 ))
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { _vibe_task_usage; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for update"; return 1; }
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status|--agent|--worktree|--branch|--next-step|--pr|--spec-standard|--spec-ref)
                [[ $# -ge 2 ]] || { vibe_die "Missing value for $1"; return 1; }
                case "$1" in
                    --status) task_status="$2" ;;
                    --agent) agent="$2" ;;
                    --worktree) worktree="$2" ;;
                    --branch) branch="$2" ;;
                    --next-step) next_step="$2" ;;
                    --pr) pr_ref="$2"; pr_mode="set" ;;
                    --spec-standard) spec_standard="$2"; spec_mode="set" ;;
                    --spec-ref) spec_ref="$2"; spec_mode="set" ;;
                esac
                shift 2
                ;;
            --github-project-item-id|--content-type)
                vibe_die "GitHub Project item identity must not be written via vibe task"
                return 1
                ;;
            --issue)
                [[ $# -ge 2 ]] || { vibe_die "Missing value for --issue"; return 1; }
                issue_refs+=("$2")
                issue_mode="append"
                shift 2
                ;;
            --roadmap-item)
                [[ $# -ge 2 ]] || { vibe_die "Missing value for --roadmap-item"; return 1; }
                roadmap_item_ids+=("$2")
                roadmap_mode="append"
                shift 2
                ;;
            --bind-current) bind_current="true"; shift ;;
            --unassign) unassign="true"; shift ;;
            -f|--force) force=1; shift ;;
            -h|--help) _vibe_task_usage; return 0 ;;
            *) vibe_die "Unknown update option: $1"; return 1 ;;
        esac
    done
    [[ -n "$task_status$agent$worktree$branch$next_step$pr_ref$spec_standard$spec_ref" || "$bind_current" == "true" || "$unassign" == "true" || "$issue_mode" == "append" || "$roadmap_mode" == "append" ]] || { vibe_die "No update fields provided"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    if [[ -n "$task_status" ]]; then
        task_status="$(_vibe_task_normalize_and_validate_status "$task_status")" || { vibe_die "Invalid task status: $task_status"; return 1; }
    fi
    if [[ "$spec_mode" == "set" ]]; then
        spec_standard="$(_vibe_task_normalize_and_validate_spec_standard "${spec_standard:-none}")" || { vibe_die "Invalid spec standard: ${spec_standard:-}"; return 1; }
    fi
    if [[ -n "$agent" ]]; then
        case "$agent" in codex|antigravity|trae|claude|opencode|kiro) ;; *) [[ "$force" -eq 1 ]] || { vibe_die "Unsupported agent: $agent"; return 1; } ;; esac
        email_slug="$agent"; [[ "$force" -eq 1 ]] && email_slug="$(_vibe_task_slugify "$agent")"
    fi
    if [[ "$unassign" == "true" ]]; then
        assigned_mode="clear"
        worktree=""
    elif [[ "$bind_current" == "true" ]]; then
        assigned_mode="set"
        target_path="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
        target_name="$(basename "$target_path")"
        worktree="$target_name"
    elif [[ -n "$worktree" ]]; then
        assigned_mode="set"
    fi
    local issue_refs_json='[]' roadmap_item_ids_json='[]'
    (( ${#issue_refs[@]} > 0 )) && issue_refs_json="$(printf '%s\n' "${issue_refs[@]}" | jq -R . | jq -s .)"
    (( ${#roadmap_item_ids[@]} > 0 )) && roadmap_item_ids_json="$(printf '%s\n' "${roadmap_item_ids[@]}" | jq -R . | jq -s .)"
    _vibe_task_validate_roadmap_items "$common_dir" "$roadmap_item_ids_json" || return 1
    [[ -z "$target_name" ]] && target_name="$worktree"
    _vibe_task_write_registry "$registry_file" "$task_id" "$task_status" "$next_step" "$worktree" "$target_path" "$branch" "$assigned_mode" "$agent" "$now" "$issue_refs_json" "$issue_mode" "$roadmap_item_ids_json" "$roadmap_mode" "$pr_ref" "$pr_mode" "$spec_standard" "$spec_ref" "$spec_mode" || return 1
    _vibe_task_sync_roadmap_links "$common_dir" "$task_id" "$roadmap_item_ids_json" "$now" || return 1
    _vibe_task_write_task_file "$common_dir" "$registry_file" "$task_id" "$now" || return 1
    _vibe_task_write_worktrees "$worktrees_file" "$target_name" "$target_path" "$task_id" "$branch" "$agent" "$bind_current" "$now" "$unassign" || return 1
    case "$task_status" in
        todo) echo "💡 Next: Create an execution scene using ${CYAN}wtnew <branch>${NC} or start with ${CYAN}vnew <branch>${NC}" ;;
        in_progress) echo "💡 Next: Ensure your cockpit is ready with ${CYAN}vup${NC}; this task record is an execution record, not a roadmap item." ;;
        completed|archived) echo "💡 Next: Cleanup with ${CYAN}vibe flow done${NC} or remove with ${CYAN}vibe task remove${NC}" ;;
    esac
    return 0
}
_vibe_task_add() {
    local task_id="" title="" common_dir registry_file task_file now tmp pr_ref="" spec_standard="none" spec_ref=""
    local -a issue_refs roadmap_item_ids
    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        echo "Usage: vibe task add <title> [--id <task-id>] [--issue <ref>]... [--roadmap-item <id>]... [--pr <ref>] [--spec-standard <standard>] [--spec-ref <ref>]"
        return 0
    fi
    if [[ $# -gt 0 && ! "$1" =~ ^-- ]]; then title="$1"; shift; fi
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title) title="$2"; shift 2 ;;
            --id) task_id="$2"; shift 2 ;;
            --issue) issue_refs+=("$2"); shift 2 ;;
            --roadmap-item) roadmap_item_ids+=("$2"); shift 2 ;;
            --pr) pr_ref="$2"; shift 2 ;;
            --spec-standard) spec_standard="$2"; shift 2 ;;
            --spec-ref) spec_ref="$2"; shift 2 ;;
            --github-project-item-id|--content-type)
                vibe_die "GitHub Project item identity must not be written via vibe task"
                return 1
                ;;
            *) vibe_die "Unknown add option: $1"; return 1 ;;
        esac
    done
    [[ -n "$title" ]] || { vibe_die "Missing title for task add"; return 1; }
    spec_standard="$(_vibe_task_normalize_and_validate_spec_standard "$spec_standard")" || { vibe_die "Invalid spec standard: $spec_standard"; return 1; }
    if [[ -z "$task_id" ]]; then local slug; slug="$(_vibe_task_slugify "$title")"; task_id="$(_vibe_task_today)-$slug"; fi
    [[ "$spec_standard" == "kiro" && -z "$spec_ref" ]] && spec_ref=".kiro/specs/$task_id"
    _vibe_task_require_plan_binding_for_add "$spec_standard" "$spec_ref" || return 1
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 && { vibe_die "Task already exists: $task_id"; return 1; }
    local issue_refs_json='[]' roadmap_item_ids_json='[]'
    (( ${#issue_refs[@]} > 0 )) && issue_refs_json="$(printf '%s\n' "${issue_refs[@]}" | jq -R . | jq -s .)"
    (( ${#roadmap_item_ids[@]} > 0 )) && roadmap_item_ids_json="$(printf '%s\n' "${roadmap_item_ids[@]}" | jq -R . | jq -s .)"
    _vibe_task_validate_roadmap_items "$common_dir" "$roadmap_item_ids_json" || return 1
    mkdir -p "$(dirname "$task_file")"; tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg title "$title" --arg now "$now" --arg pr_ref "$pr_ref" --arg spec_standard "$spec_standard" --arg spec_ref "$spec_ref" --argjson issue_refs "$issue_refs_json" --argjson roadmap_item_ids "$roadmap_item_ids_json" \
      '.tasks += [{
        task_id:$task_id,
        title:$title,
        description:null,
        status:"todo",
        source_type:"local",
        source_refs:[],
        roadmap_item_ids:$roadmap_item_ids,
        issue_refs:$issue_refs,
        pr_ref:(if $pr_ref == "" then null else $pr_ref end),
        related_task_ids:[],
        current_subtask_id:null,
        subtasks:[],
        runtime_worktree_name:null,
        runtime_worktree_path:null,
        runtime_branch:null,
        runtime_agent:null,
        assigned_worktree:null,
        spec_standard:$spec_standard,
        spec_ref:(if $spec_ref == "" then null else $spec_ref end),
        next_step:null,
        created_at:$now,
        updated_at:$now,
        completed_at:null,
        archived_at:null
      }]' "$registry_file" > "$tmp" && mv "$tmp" "$registry_file" || return 1
    jq -n --arg task_id "$task_id" --arg title "$title" --arg now "$now" --arg pr_ref "$pr_ref" --arg spec_standard "$spec_standard" --arg spec_ref "$spec_ref" --argjson issue_refs "$issue_refs_json" --argjson roadmap_item_ids "$roadmap_item_ids_json" \
      '{
        task_id:$task_id,
        title:$title,
        description:null,
        status:"todo",
        source_type:"local",
        source_refs:[],
        roadmap_item_ids:$roadmap_item_ids,
        issue_refs:$issue_refs,
        pr_ref:(if $pr_ref == "" then null else $pr_ref end),
        related_task_ids:[],
        current_subtask_id:null,
        subtasks:[],
        runtime_worktree_name:null,
        runtime_worktree_path:null,
        runtime_branch:null,
        runtime_agent:null,
        assigned_worktree:null,
        spec_standard:$spec_standard,
        spec_ref:(if $spec_ref == "" then null else $spec_ref end),
        next_step:null,
        created_at:$now,
        updated_at:$now,
        completed_at:null,
        archived_at:null
      }' > "$task_file"
    _vibe_task_sync_roadmap_links "$common_dir" "$task_id" "$roadmap_item_ids_json" "$now" || return 1
    log_success "Task added: $task_id"
    echo "💡 Next: Run ${CYAN}wtnew <branch>${NC} or ${CYAN}vnew <branch>${NC} to start an execution scene, then bind this execution record."
}
_vibe_task_branch_matches_any() { local branch="$1" candidate; shift; for candidate in "$@"; do [[ -n "$candidate" && ( "$branch" == "$candidate" || "$branch" == */"$candidate" ) ]] && return 0; done; return 1; }
_vibe_task_remove() {
    local assume_yes=false task_id="" common_dir registry_file worktrees_file task_file tmp
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                echo "Usage: vibe task remove [--yes] <task-id>"
                return 0
                ;;
            -y|--yes)
                assume_yes=true
                shift
                ;;
            *)
                if [[ -n "$task_id" ]]; then
                    vibe_die "Unexpected argument: $1"
                    return 1
                fi
                task_id="$1"
                shift
                ;;
        esac
    done
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for remove"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg tid "$task_id" '.worktrees[]? | select(.current_task == $tid or (.tasks // [] | index($tid) != null))' "$worktrees_file" >/dev/null 2>&1 \
        && { vibe_die "Task $task_id is still bound to a worktree. Unbind it first via 'vibe flow bind none'."; return 1; }
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    local indexed_branch task_title="" task_suffix="" task_slug="" local_branches="" remote_branches="" residual_local="" residual_remote=""
    local -a branch_candidates local_matches remote_matches
    indexed_branch=$(jq -r --arg tid "$task_id" '.tasks[]? | select(.task_id == $tid) | .runtime_branch // empty' "$registry_file" | head -1)
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
        if [[ "$assume_yes" != true ]]; then
            vibe_die "Branch cleanup required before removing task $task_id; rerun with --yes."
            return 1
        fi
        while read -r lb; do [[ -n "$lb" ]] && vibe_delete_local_branch "$lb" || residual_local+="$lb\n"; done <<< "$local_branches"
        while read -r rb; do
            [[ -z "$rb" ]] && continue
            local rb_name="${rb#origin/}"
            vibe_delete_remote_branch "$rb_name" || residual_remote+="$rb_name\n"
        done <<< "$remote_branches"
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
