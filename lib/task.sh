#!/usr/bin/env zsh

_vibe_task_common_dir() { git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { vibe_die "Not in a git repository"; return 1; }; git rev-parse --git-common-dir; }
_vibe_task_now() { date +"%Y-%m-%dT%H:%M:%S%z"; }
_vibe_task_today() { date +"%Y-%m-%d"; }
_vibe_task_slug_max_len() { local n="${VIBE_TASK_SLUG_MAX_LEN:-48}"; [[ "$n" =~ ^[0-9]+$ && "$n" -ge 8 ]] || n=48; echo "$n"; }
_vibe_task_is_path_like() {
    local raw="$1" head="${1%%/*}" tail="${1:t}"
    [[ "$raw" == */* && "$raw" != *" "* ]] || return 1
    [[ "$raw" == /* || "$raw" == ./* || "$raw" == ../* || "$raw" == ~/* || "$tail" == *.* ]] && return 0
    case "$head" in docs|doc|plans|src|lib|tests|scripts|skills|openspec|config|bin|.agent|.kiro) return 0 ;; esac
    return 1
}
_vibe_task_slug_seed() { local raw="$1" seed="$1"; _vibe_task_is_path_like "$raw" && { seed="${raw:t}"; [[ "$seed" == *.md ]] && seed="${seed%.md}"; }; print -r -- "$seed"; }
_vibe_task_slug_hash8() { local raw="$1" hash; hash="$(print -r -- "$raw" | shasum 2>/dev/null | awk '{print $1}')"; [[ -n "$hash" ]] || hash="$(print -r -- "$raw" | cksum | awk '{print $1}')"; print -r -- "${hash[1,8]}"; }
_vibe_task_slugify() {
    local seed slug max_len hash keep_len; seed="$(_vibe_task_slug_seed "$1")"
    slug="$(print -r -- "$seed" | tr '[:upper:]' '[:lower:]' | sed -E "s/[^a-z0-9]+/-/g; s/^-+//; s/-+$//")"
    [[ -n "$slug" ]] || slug="task"
    max_len="$(_vibe_task_slug_max_len)"
    if (( ${#slug} > max_len )); then
        hash="$(_vibe_task_slug_hash8 "$1")"
        keep_len=$(( max_len - 9 ))
        (( keep_len < 1 )) && keep_len=1
        slug="${slug[1,$keep_len]}-${hash}"
    fi
    [[ -n "$slug" ]] || slug="task"
    print -r -- "$slug"
}
_vibe_task_require_file() { [[ -f "$1" ]] || { vibe_die "Missing $2: $1"; return 1; }; }
_vibe_task_task_file() { echo "$1/vibe/tasks/$2/task.json"; }

source "$VIBE_LIB/task_render.sh"
source "$VIBE_LIB/task_write.sh"
source "$VIBE_LIB/task_help.sh"
source "$VIBE_LIB/task_query.sh"
source "$VIBE_LIB/task_actions.sh"

vibe_task() {
    local subcommand="${1:-list}"
    case "$subcommand" in
        list) [[ $# -gt 0 ]] && shift; _vibe_task_list "$@" ;;
        add) [[ $# -gt 0 ]] && shift; _vibe_task_add "$@" ;;
        update) [[ $# -gt 0 ]] && shift; _vibe_task_update "$@" ;;
        remove) [[ $# -gt 0 ]] && shift; _vibe_task_remove "$@" ;;
        sync) [[ $# -gt 0 ]] && shift; _vibe_task_sync "$@" ;;
        -h|--help|help) _vibe_task_usage ;;
        -*) _vibe_task_list "$@" ;;
        "") _vibe_task_list ;;
        *) vibe_die "Unknown task subcommand: $subcommand"; return 1 ;;
    esac
}
