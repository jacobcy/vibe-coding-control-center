#!/usr/bin/env zsh

_vibe_task_common_dir() { vibe_git_dir; }
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
_vibe_task_normalize_status() {
    local raw="$1"
    case "$raw" in
        review) echo "in_progress" ;;
        done|merged) echo "completed" ;;
        skipped) echo "archived" ;;
        *) echo "$raw" ;;
    esac
}
_vibe_task_is_valid_status() {
    case "$1" in
        todo|in_progress|blocked|completed|archived) return 0 ;;
        *) return 1 ;;
    esac
}
_vibe_task_is_valid_spec_standard() {
    case "$1" in
        openspec|kiro|superpowers|supervisor|none) return 0 ;;
        *) return 1 ;;
    esac
}
_vibe_task_normalize_spec_standard() {
    local raw="${1:-none}"
    [[ -n "$raw" ]] || raw="none"
    echo "${raw:l}"
}
_vibe_task_normalize_and_validate_spec_standard() {
    local normalized
    normalized="$(_vibe_task_normalize_spec_standard "$1")"
    _vibe_task_is_valid_spec_standard "$normalized" || return 1
    echo "$normalized"
}
_vibe_task_normalize_and_validate_status() {
    local normalized
    normalized="$(_vibe_task_normalize_status "$1")"
    _vibe_task_is_valid_status "$normalized" || return 1
    echo "$normalized"
}

source "$VIBE_LIB/task_render.sh"
source "$VIBE_LIB/task_write.sh"
source "$VIBE_LIB/task_help.sh"
source "$VIBE_LIB/task_query_openspec.sh"
source "$VIBE_LIB/task_query.sh"
source "$VIBE_LIB/task_list.sh"
source "$VIBE_LIB/task_show.sh"
source "$VIBE_LIB/task_roadmap_links.sh"
source "$VIBE_LIB/task_actions.sh"
source "$VIBE_LIB/task_audit.sh"

vibe_task() {
    local subcommand="${1:-list}"
    case "$subcommand" in
        list) [[ $# -gt 0 ]] && shift; _vibe_task_list "$@" ;;
        show) [[ $# -gt 0 ]] && shift; _vibe_task_show "$@" ;;
        add) [[ $# -gt 0 ]] && shift; _vibe_task_add "$@" ;;
        update) [[ $# -gt 0 ]] && shift; _vibe_task_update "$@" ;;
        remove) [[ $# -gt 0 ]] && shift; _vibe_task_remove "$@" ;;
        audit) [[ $# -gt 0 ]] && shift; vibe_task_audit "$@" ;;
        count-by-branch) [[ $# -gt 0 ]] && shift; _vibe_task_count_by_branch "$@" ;;
        -h|--help|help) _vibe_task_usage ;;
        -*) _vibe_task_list "$@" ;;
        "") _vibe_task_list ;;
        *) vibe_die "Unknown task subcommand: $subcommand"; return 1 ;;
    esac
}
