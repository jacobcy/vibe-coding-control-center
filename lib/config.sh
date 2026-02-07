#!/usr/bin/env zsh
# Enhanced Configuration Management for Vibe Coding Control Center

# Configuration variables with default values
declare -A VIBE_CONFIG

# Initialize configuration values
initialize_config() {
    local script_dir_realpath="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"

    # Base configuration
    VIBE_CONFIG[ROOT_DIR]="$script_dir_realpath"
    VIBE_CONFIG[LIB_DIR]="${script_dir_realpath}/lib"
    VIBE_CONFIG[CONFIG_DIR]="${script_dir_realpath}/config"
    VIBE_CONFIG[INSTALL_DIR]="${script_dir_realpath}/install"
    VIBE_CONFIG[SCRIPTS_DIR]="${script_dir_realpath}/scripts"
    VIBE_CONFIG[TESTS_DIR]="${script_dir_realpath}/tests"
    VIBE_CONFIG[DOCS_DIR]="${script_dir_realpath}/docs"

    # Runtime configuration
    VIBE_CONFIG[TEMP_DIR]="${TMPDIR:-/tmp}"
    VIBE_CONFIG[LOG_LEVEL]="INFO"

    # API configuration defaults
    VIBE_CONFIG[ANTHROPIC_BASE_URL]="https://api.anthropic.com"
    VIBE_CONFIG[ANTHROPIC_MODEL]="claude-3-5-sonnet-20241022"

    # Security settings
    VIBE_CONFIG[MAX_PATH_LENGTH]=4096
    VIBE_CONFIG[MAX_INPUT_LENGTH]=10000
}

# Load user-specific configuration
load_user_config() {
    local config_file="${1:-$VIBE_CONFIG[CONFIG_DIR]/config.local}"

    if [[ -f "$config_file" ]]; then
        # Validate the config file before sourcing
        if validate_path "$config_file" "Configuration file validation failed"; then
            source "$config_file"
        else
            log_warn "Invalid configuration file: $config_file"
            return 1
        fi
    fi
}

# Get a configuration value
config_get() {
    local key="$1"
    local default_value="${2:-}"

    if [[ -n "${VIBE_CONFIG[$key]+isset}" ]]; then
        echo "${VIBE_CONFIG[$key]}"
    else
        echo "$default_value"
    fi
}

# Set a configuration value
config_set() {
    local key="$1"
    local value="$2"

    # Validate inputs
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

# Check if a configuration key exists
config_exists() {
    local key="$1"
    [[ -n "${VIBE_CONFIG[$key]+isset}" ]]
}

# Load configuration
initialize_config
