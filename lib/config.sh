#!/usr/bin/env zsh

typeset -gA VIBE_CONFIG

# Auto-detect VIBE_ROOT (project root directory).
# VIBE_HOME is always derived as $VIBE_ROOT/.vibe — never configured separately.
#
# Search order:
#   1. This script's own location (lib/config.sh → parent = project root)
#   2. Caller-set VIBE_ROOT (bin/vibe-* set it before sourcing us)
#   3. PWD upward walk looking for .vibe/
#   4. Git repository root
#   5. $HOME (fallback — $HOME/.vibe as global config)
_find_vibe_root() {
    # 1. Infer from this script's own location — most reliable
    local _dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"
    local _root="$(cd "${_dir}/.." && pwd)"
    if [[ -d "${_root}/.vibe" && -d "${_root}/bin" && -d "${_root}/lib" ]]; then
        echo "${_root}"
        return
    fi

    # 2. Caller already set VIBE_ROOT (e.g. bin/vibe-env line 6)
    if [[ -n "${VIBE_ROOT:-}" && -d "${VIBE_ROOT}/.vibe" ]]; then
        echo "${VIBE_ROOT}"
        return
    fi

    # 3. Walk up from PWD looking for a .vibe directory
    local _cur="$PWD"
    while [[ "$_cur" != "/" ]]; do
        if [[ -d "${_cur}/.vibe" ]]; then
            echo "${_cur}"
            return
        fi
        _cur="$(dirname "${_cur}")"
    done

    # 4. Git repository root
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        local _gr="$(git rev-parse --show-toplevel)"
        if [[ -d "${_gr}/.vibe" ]]; then
            echo "${_gr}"
            return
        fi
    fi

    # 5. Fallback — treat $HOME as the root ($HOME/.vibe is global config)
    echo "$HOME"
}

VIBE_ROOT="$(_find_vibe_root)"
VIBE_HOME="$VIBE_ROOT/.vibe"

initialize_config() {
    local script_dir_realpath="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"

    VIBE_CONFIG[ROOT_DIR]="$script_dir_realpath"
    VIBE_CONFIG[LIB_DIR]="${script_dir_realpath}/lib"
    VIBE_CONFIG[CONFIG_DIR]="$VIBE_HOME"
    VIBE_CONFIG[PROJECT_CONFIG_DIR]="${script_dir_realpath}/config"
    VIBE_CONFIG[INSTALL_DIR]="${script_dir_realpath}/install"
    VIBE_CONFIG[SCRIPTS_DIR]="${script_dir_realpath}/scripts"
    VIBE_CONFIG[TESTS_DIR]="${script_dir_realpath}/tests"
    VIBE_CONFIG[DOCS_DIR]="${script_dir_realpath}/docs"

    VIBE_CONFIG[TEMP_DIR]="${TMPDIR:-/tmp}"
    VIBE_CONFIG[LOG_LEVEL]="INFO"

    VIBE_CONFIG[ANTHROPIC_BASE_URL]="https://api.bghunt.cn"
    VIBE_CONFIG[ANTHROPIC_MODEL]="claude-3-5-sonnet-20241022"

    VIBE_CONFIG[MAX_PATH_LENGTH]=4096
    VIBE_CONFIG[MAX_INPUT_LENGTH]=10000
}

load_keys() {
    [[ -f "$VIBE_HOME/keys.env" ]] || return 0

    local _lines=("${(@f)$(< "$VIBE_HOME/keys.env")}")
    local _l
    for _l in "${_lines[@]}"; do
        [[ "$_l" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${_l//[[:space:]]/}" ]] && continue
        if [[ "$_l" == *=* ]]; then
            local _k="${_l%%=*}"
            local _v="${_l#*=}"
            typeset -g "VIBE_CONFIG[KEY_${_k}]"="$_v"
        fi
    done
}

export_keys() {
    local keys_file="$VIBE_HOME/keys.env"
    [[ -f "$keys_file" ]] || { log_warn "keys.env not found at $keys_file"; return 1; }

    set -a
    source "$keys_file"
    set +a
}

load_toml_config() {
    local toml_file="${1:-$VIBE_HOME/config.toml}"
    # Fallback to legacy path if new path doesn't exist
    if [[ ! -f "$toml_file" && -f "$HOME/.codex/config.toml" ]]; then
        toml_file="$HOME/.codex/config.toml"
    fi
    [[ -f "$toml_file" ]] || return 0

    while IFS= read -r line || [[ -n "$line" ]]; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue
        [[ "$line" =~ ^\[.*\]$ ]] && continue

        if [[ "$line" =~ ^[[:space:]]*([a-zA-Z0-9_-]+)[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$ ]]; then
            local key="${match[1]}"
            local value="${match[2]}"
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"
            VIBE_CONFIG[$key]="$value"
        fi
    done < "$toml_file"
}

load_user_config() {
    local config_file="${1:-$VIBE_HOME/config.local}"

    if [[ -f "$config_file" ]]; then
        if validate_path "$config_file" "Configuration file validation failed"; then
            source "$config_file"
        else
            log_warn "Invalid configuration file: $config_file"
            return 1
        fi
    fi

    load_keys
    load_toml_config
}

config_get() {
    local key="$1"
    local default_value="${2:-}"
    if [[ -n "${VIBE_CONFIG[$key]+isset}" ]]; then
        echo "${VIBE_CONFIG[$key]}"
    else
        echo "$default_value"
    fi
}

config_set() {
    local key="$1"
    local value="$2"
    if ! validate_input "$key" "false"; then
        log_error "Invalid configuration key: $key"
        return 1
    fi
    if ! validate_input "$value" "true"; then
        log_error "Invalid configuration value for key: $key"
        return 1
    fi
    VIBE_CONFIG[$key]="$value"
}

config_exists() {
    local key="$1"
    [[ -n "${VIBE_CONFIG[$key]+isset}" ]]
}

config_get_key() {
    local key="$1"
    local config_key="KEY_$key"
    if [[ -n "${VIBE_CONFIG[$config_key]+isset}" ]]; then
        echo "${VIBE_CONFIG[$config_key]}"
    fi
}

initialize_config
