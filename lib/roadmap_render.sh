#!/usr/bin/env zsh
# lib/roadmap_render.sh - Rendering helpers for Roadmap module

_vibe_roadmap_fd_is_tty() {
    [[ -t "$1" ]]
}

_vibe_roadmap_supports_color() {
    _vibe_roadmap_fd_is_tty 1 || _vibe_roadmap_fd_is_tty 0
}

_vibe_roadmap_format() {
    local prefix="$1" text="$2"
    if _vibe_roadmap_supports_color; then
        printf '%s%s%s' "$prefix" "$text" "$NC"
    else
        printf '%s' "$text"
    fi
}

_vibe_roadmap_status_color_code() {
    local item_status="$1"
    case "$item_status" in
        p0) printf '%s' "${RED}${BOLD}" ;;
        current) printf '%s' "${GREEN}${BOLD}" ;;
        next) printf '%s' "${BLUE}${BOLD}" ;;
        deferred) printf '%s' "${YELLOW}${BOLD}" ;;
        rejected) printf '%s' "$(printf '\033[1;90m')" ;;
        *) printf '%s' "$NC" ;;
    esac
}

_vibe_roadmap_color_status() {
    local item_status="$1"
    case "$item_status" in
        rejected) _vibe_roadmap_format "$(printf '\033[0;90m')" "$item_status" ;;
        p0|current|next|deferred) _vibe_roadmap_format "$(_vibe_roadmap_status_color_code "$item_status")" "$item_status" ;;
        *) printf '%s' "$item_status" ;;
    esac
}

_vibe_roadmap_status_label() {
    local item_status="$1"
    case "$item_status" in
        p0) printf 'P0' ;;
        current) printf 'Current' ;;
        next) printf 'Next' ;;
        deferred) printf 'Deferred' ;;
        rejected) printf 'Rejected' ;;
        *) printf '%s' "$item_status" ;;
    esac
}

_vibe_roadmap_group_heading() {
    local item_status="$1" count="$2" label
    label="$(_vibe_roadmap_status_label "$item_status")"
    _vibe_roadmap_format "$(_vibe_roadmap_status_color_code "$item_status")" "${label} (${count})"
}
