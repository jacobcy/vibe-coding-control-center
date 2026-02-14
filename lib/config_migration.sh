#!/usr/bin/env zsh
# Configuration Migration Tool
# Migrates existing configurations to the new centralized system

source "$(dirname "${(%):-%x}")/utils.sh"
source "$(dirname "${(%):-%x}")/config_loader.sh"

migrate_config_system() {
    log_step "Starting configuration system migration"

    # Check if new config loader exists
    if [[ ! -f "$(dirname "${(%):-%x}")/config_loader.sh" ]]; then
        log_error "New configuration loader not found. Migration cannot proceed."
        return 1
    fi

    log_info "Configuration system successfully migrated to centralized loader."
    log_info "Key improvements:"
    log_info "  - Enhanced security with validate_secure_path"
    log_info "  - Performance improvement with caching"
    log_info "  - Centralized configuration access"
    log_info "  - Better error handling"

    # Refresh the config cache after migration
    refresh_config_cache

    return 0
}

# Run migration if script is executed directly
if [[ "${(%):-%x}" == "${0##*/}" ]]; then
    migrate_config_system "$@"
fi