#!/usr/bin/env zsh

# Source the new configuration loader
source "$(dirname "${(%):-%x}")/config_loader.sh"

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
    # Check for either .vibe OR config directory to identify root
    if [[ (-d "${_root}/.vibe" || -d "${_root}/config") && -d "${_root}/bin" && -d "${_root}/lib" ]]; then
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

_find_vibe_home() {
    # 1. Caller specified override
    if [[ -n "${VIBE_HOME_OVERRIDE:-}" ]]; then
        echo "$VIBE_HOME_OVERRIDE"
        return
    fi

    # 2. Walk up from PWD looking for .vibe directory (Local Project Config)
    local _cur="$PWD"
    while [[ "$_cur" != "/" ]]; do
        if [[ -d "${_cur}/.vibe" ]]; then
            echo "${_cur}/.vibe"
            return
        fi
        _cur="$(dirname "${_cur}")"
    done

    # 3. Git repository root (Local Project Config)
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        local _gr="$(git rev-parse --show-toplevel)"
        if [[ -d "${_gr}/.vibe" ]]; then
            echo "${_gr}/.vibe"
            return
        fi
    fi

    # 4. Fallback to VIBE_ROOT/.vibe (Installation Config)
    if [[ -d "${VIBE_ROOT}/.vibe" ]]; then
        echo "${VIBE_ROOT}/.vibe"
        return
    fi
    
    # 5. Fallback to $HOME/.vibe (Global User Config)
    echo "$HOME/.vibe"
}

VIBE_ROOT="$(_find_vibe_root)"
VIBE_HOME="$(_find_vibe_home)"

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

    VIBE_CONFIG[ANTHROPIC_BASE_URL]="${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"
    VIBE_CONFIG[ANTHROPIC_MODEL]="claude-sonnet-4-5"

    VIBE_CONFIG[MAX_PATH_LENGTH]=4096
    VIBE_CONFIG[MAX_INPUT_LENGTH]=10000
}

load_keys() {
    # Use the centralized config loader for security
    load_configuration
}

export_keys() {
    # Use the centralized config loader for security
    load_configuration

    # Export keys from the cached config values
    for key in "${(@k)CONFIG_CACHE}"; do
        export "$key=${CONFIG_CACHE[$key]}"
    done
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

open_editor() {
    local file="$1"
    local editor=""

    # 1. Check VIBE_EDITOR from keys.env
    load_keys
    local vibe_editor="${VIBE_CONFIG[KEY_VIBE_EDITOR]:-}"
    if [[ -n "$vibe_editor" ]]; then
        # Handle cases where editor command might have spaces (e.g. "code -w")
        # For simplicity, assume first word is command
        local cmd="${vibe_editor%% *}"
        if command -v "$cmd" >/dev/null 2>&1; then
             editor="$vibe_editor"
        else
             log_warn "Configured editor '$vibe_editor' not found."
        fi
    fi

    # 2. Check EDITOR env var
    if [[ -z "$editor" && -n "${EDITOR:-}" ]]; then
        editor="$EDITOR"
    fi

    # 3. Auto-detect popular editors (IDE first)
    if [[ -z "$editor" ]]; then
        if command -v code >/dev/null 2>&1; then editor="code"; fi
    fi
    if [[ -z "$editor" ]]; then
        if command -v trae >/dev/null 2>&1; then editor="trae"; fi
    fi
    if [[ -z "$editor" ]]; then
        if command -v cursor >/dev/null 2>&1; then editor="cursor"; fi
    fi
    if [[ -z "$editor" ]]; then
        if command -v windsurf >/dev/null 2>&1; then editor="windsurf"; fi
    fi
    if [[ -z "$editor" ]]; then
        if command -v vim >/dev/null 2>&1; then editor="vim"; fi
    fi
     if [[ -z "$editor" ]]; then
        if command -v nano >/dev/null 2>&1; then editor="nano"; fi
    fi

    # 4. Fallback
    if [[ -z "$editor" ]]; then
        editor="vi"
    fi

    log_info "Opening with $editor..."
    # Execute editor with file
    # Use eval to handle arguments in editor string if present (e.g. "code -w")
    # But eval is risky. Let's split string properly if needed.
    # Zsh array splitting is safe: ${(0)editor}
    # But better: just rely on word splitting for simple cases or shell execution
    # For robust handling:
    if [[ "$editor" == *" "* ]]; then
        eval "$editor" "\"$file\""
    else
        "$editor" "$file"
    fi
}

# =====================
# vibe.yaml Configuration Support
# =====================

# Parse vibe.yaml configuration file
# Usage: parse_vibe_yaml [yaml_file]
# Default: $VIBE_HOME/vibe.yaml
# Populates VIBE_YAML_CONFIG associative array
typeset -gA VIBE_YAML_CONFIG

parse_vibe_yaml() {
    local yaml_file="${1:-$VIBE_HOME/vibe.yaml}"

    if [[ ! -f "$yaml_file" ]]; then
        return 1
    fi

    # Reset config
    VIBE_YAML_CONFIG=()

    local current_section=""
    local current_subsection=""
    local indent_level=0
    local prev_indent=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line//[[:space:]]/}" ]] && continue

        # Count leading spaces for indentation
        local stripped="${line#"${line%%[![:space:]]*}"}"
        local leading_spaces=$((${#line} - ${#stripped}))
        line="$stripped"

        # Remove trailing whitespace
        line="${line%"${line##*[![:space:]]}"}"

        # Determine nesting level (2 spaces = 1 level)
        indent_level=$((leading_spaces / 2))

        # Reset subsection when going back to lower indent
        if [[ $indent_level -lt $prev_indent ]]; then
            current_subsection=""
        fi
        prev_indent=$indent_level

        # Detect list items (e.g., "- github")
        if [[ "$line" =~ ^-[[:space:]]*(.+)$ ]]; then
            local item="${match[1]}"
            # Store as section_items
            local list_key="${current_section}_items"
            if [[ -n "${VIBE_YAML_CONFIG[$list_key]:-}" ]]; then
                VIBE_YAML_CONFIG[$list_key]="${VIBE_YAML_CONFIG[$list_key]} ${item}"
            else
                VIBE_YAML_CONFIG[$list_key]="$item"
            fi
            continue
        fi

        # Parse key: value pairs
        if [[ "$line" =~ ^([a-zA-Z_][a-zA-Z0-9_-]*):[[:space:]]*(.*)$ ]]; then
            local key="${match[1]}"
            local value="${match[2]}"
            value="${value%"${value##*[![:space:]]}"}"

            # Remove quotes from value if present
            value="${value#\"}"
            value="${value%\"}"
            value="${value#\'}"
            value="${value%\'}"

            if [[ $indent_level -eq 0 ]]; then
                # Top-level
                if [[ -n "$value" ]]; then
                    # Has value -> store directly
                    VIBE_YAML_CONFIG[$key]="$value"
                    current_section=""
                    current_subsection=""
                else
                    # No value -> this is a section
                    current_section="$key"
                    current_subsection=""
                fi
            elif [[ $indent_level -eq 1 ]]; then
                # First level under section
                if [[ -n "$value" ]]; then
                    # Has value -> store as section_key
                    VIBE_YAML_CONFIG[${current_section}_${key}]="$value"
                else
                    # No value -> this is a subsection
                    current_subsection="$key"
                fi
            elif [[ $indent_level -ge 2 ]]; then
                # Deeper nesting
                if [[ -n "$value" ]]; then
                    # Has value -> store as section_subsection_key
                    if [[ -n "$current_subsection" ]]; then
                        VIBE_YAML_CONFIG[${current_section}_${current_subsection}_${key}]="$value"
                    else
                        VIBE_YAML_CONFIG[${current_section}_${key}]="$value"
                    fi
                fi
            fi
            continue
        fi
    done < "$yaml_file"

    return 0
}

# Get a value from vibe.yaml
# Usage: vibe_yaml_get <key> [default_value]
# Examples:
#   vibe_yaml_get "version"
#   vibe_yaml_get "keys_current"
#   vibe_yaml_get "tools_claude_enabled"
vibe_yaml_get() {
    local key="$1"
    local default_value="${2:-}"

    if [[ -n "${VIBE_YAML_CONFIG[$key]+isset}" ]]; then
        echo "${VIBE_YAML_CONFIG[$key]}"
    else
        echo "$default_value"
    fi
}

# Get list items from vibe.yaml
# Usage: vibe_yaml_get_list <section>
# Example: vibe_yaml_get_list "mcp" -> "github brave-search"
vibe_yaml_get_list() {
    local section="$1"
    local key="${section}_items"
    echo "${VIBE_YAML_CONFIG[$key]:-}"
}

# Get current keys group name
# Usage: get_current_keys_group
# Returns: "anthropic", "openai", etc.
get_current_keys_group() {
    # First, try the symlink
    local current_link="$VIBE_HOME/keys/current"

    if [[ -L "$current_link" ]]; then
        local target
        # macOS compatible: readlink without -f
        target=$(readlink "$current_link" 2>/dev/null)
        if [[ -n "$target" ]]; then
            # Extract basename without .env extension
            target=$(basename "$target" .env)
            echo "$target"
            return 0
        fi
    fi

    # Fallback to vibe.yaml
    if parse_vibe_yaml 2>/dev/null; then
        local yaml_current=$(vibe_yaml_get "keys_current" "")
        if [[ -n "$yaml_current" ]]; then
            echo "$yaml_current"
            return 0
        fi
    fi

    # Default fallback
    echo "anthropic"
}

# Set current keys group (updates symlink and vibe.yaml)
# Usage: set_current_keys_group <group_name>
set_current_keys_group() {
    local group="$1"

    if [[ -z "$group" ]]; then
        log_error "Group name required"
        return 1
    fi

    local target_file="$VIBE_HOME/keys/${group}.env"

    if [[ ! -f "$target_file" ]]; then
        log_error "Key group not found: $group"
        return 1
    fi

    # Update symlink (use relative path for portability)
    local current_link="$VIBE_HOME/keys/current"
    ln -sfn "${group}.env" "$current_link"

    # Update vibe.yaml if it exists
    local yaml_file="$VIBE_HOME/vibe.yaml"
    if [[ -f "$yaml_file" ]]; then
        # Simple in-place update for keys.current
        if command -v sed >/dev/null 2>&1; then
            # macOS sed requires -i ''
            sed -i '' "s/^\([[:space:]]*current:[[:space:]]*\).*/\1$group/" "$yaml_file" 2>/dev/null || \
            sed -i "s/^\([[:space:]]*current:[[:space:]]*\).*/\1$group/" "$yaml_file" 2>/dev/null
        fi
    fi

    return 0
}

initialize_config
