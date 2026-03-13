#!/usr/bin/env zsh

_vibe_task_collect_openspec_tasks() {
    local repo_root="$1"
    local changes_dir="$repo_root/openspec/changes" aggregate_file change_dir change_name
    local bridge_script="$VIBE_ROOT/scripts/openspec_bridge.sh"
    local task_json tasks_file total_tasks done_tasks change_status next_step

    [[ -d "$changes_dir" ]] || { echo '{"tasks":[]}'; return 0; }

    aggregate_file="$(mktemp)" || return 1
    echo '[]' > "$aggregate_file"
    { setopt nullglob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true

    for change_dir in "$changes_dir"/*; do
        [[ -d "$change_dir" ]] || continue
        change_name="$(basename "$change_dir")"
        [[ "$change_name" == "archive" ]] && continue

        task_json=""
        if [[ -f "$bridge_script" ]]; then
            task_json="$(cd "$repo_root" && zsh "$bridge_script" find "$change_name" 2>/dev/null || true)"
            if [[ -n "$task_json" ]] && echo "$task_json" | jq -e . >/dev/null 2>&1; then
                task_json="$(echo "$task_json" | jq -c --arg cid "$change_name" '{
                    task_id: (.task_id // $cid),
                    title: (.title // $cid),
                    framework: (.framework // "openspec"),
                    source_path: (.source_path // ("openspec/changes/" + $cid)),
                    status: (.status // "todo"),
                    spec_standard: "openspec",
                    spec_ref: (.source_path // ("openspec/changes/" + $cid)),
                    current_subtask_id: null,
                    runtime_worktree_name: null,
                    assigned_worktree: null,
                    next_step: (.next_step // ("Continue OpenSpec change: openspec/changes/" + $cid + "/tasks.md"))
                }')"
            else
                task_json=""
            fi
        fi

        if [[ -z "$task_json" ]]; then
            tasks_file="$change_dir/tasks.md"
            total_tasks=0
            done_tasks=0
            if [[ -f "$tasks_file" ]]; then
                total_tasks="$(grep -E '^- \[( |x|X)\]' "$tasks_file" 2>/dev/null | wc -l | tr -d ' ')"
                done_tasks="$(grep -E '^- \[[xX]\]' "$tasks_file" 2>/dev/null | wc -l | tr -d ' ')"
            fi
            if [[ "$total_tasks" -gt 0 && "$done_tasks" -eq "$total_tasks" ]]; then
                change_status="completed"
            elif [[ "$done_tasks" -gt 0 ]]; then
                change_status="in_progress"
            else
                change_status="todo"
            fi
            next_step="Continue OpenSpec change: openspec/changes/$change_name/tasks.md"
            task_json="$(jq -nc --arg task_id "$change_name" --arg title "$change_name" \
                --arg framework "openspec" --arg source_path "openspec/changes/$change_name" \
                --arg status "$change_status" --arg next_step "$next_step" \
                '{task_id:$task_id,title:$title,framework:$framework,source_path:$source_path,status:$status,spec_standard:"openspec",spec_ref:$source_path,current_subtask_id:null,runtime_worktree_name:null,assigned_worktree:null,next_step:$next_step}')"
        fi

        jq --argjson t "$task_json" '. += [$t]' "$aggregate_file" > "$aggregate_file.tmp" && mv "$aggregate_file.tmp" "$aggregate_file"
    done

    jq -n --slurpfile tasks "$aggregate_file" '{"tasks":($tasks[0] // [])}'
    rm -f "$aggregate_file"
}
