#!/usr/bin/env zsh
# lib/capabilities/template.sh - Capability Module Template
# Copy this file to create a new capability
#
# USAGE:
#   1. Copy this file: cp lib/capabilities/template.sh lib/capabilities/my_capability.sh
#   2. Replace "template" with your capability name (search and replace)
#   3. Implement the required functions
#   4. Remove or replace this header comment

# ── Capability Metadata ───────────────────────────────────
readonly CAPABILITY_NAME="template"
readonly CAPABILITY_VERSION="1.0.0"
readonly CAPABILITY_DESCRIPTION="Template capability module"

# ── Capability Initialization ─────────────────────────────
# Called when capability is discovered by the registry
# Usage: vibe_<name>_init
vibe_template_init() {
    # Register this capability with metadata
    vibe_register_capability "$CAPABILITY_NAME" "$CAPABILITY_VERSION" "$CAPABILITY_DESCRIPTION"

    # Declare dependencies (if any)
    # vibe_declare_deps "$CAPABILITY_NAME" "dep1" "dep2"

    # Initialize capability-specific state
    # ...
}

# ── Hook Registration ─────────────────────────────────────
# Called by lifecycle system to register hooks
# Usage: vibe_<name>_register_hooks
vibe_template_register_hooks() {
    # Register before hooks
    # vibe_register_before_hook "command" "hook_function"

    # Register after hooks
    # vibe_register_after_hook "command" "hook_function"
}

# ── Main Capability Function ──────────────────────────────
# Main entry point for the capability
# Usage: vibe_<name> [args...]
vibe_template() {
    local action="${1:-help}"
    shift 2>/dev/null || true

    case "$action" in
        help|--help|-h)
            vibe_template_help
            ;;
        *)
            # Default action
            log_info "Template capability executed with action: $action"
            log_info "Arguments: $@"
            ;;
    esac
}

# ── Capability Help ───────────────────────────────────────
# Display help information for the capability
vibe_template_help() {
    echo "${BOLD}vibe ${CAPABILITY_NAME}${NC} - ${CAPABILITY_DESCRIPTION}"
    echo ""
    echo "Usage: ${CYAN}vibe ${CAPABILITY_NAME}${NC} <action> [args]"
    echo ""
    echo "Actions:"
    echo "  ${GREEN}help${NC}     Show this help message"
    echo ""
    echo "Examples:"
    echo "  vibe ${CAPABILITY_NAME} help"
}

# ── Capability Helper Functions ───────────────────────────
# Add your helper functions here
# Prefix with _vibe_template_ to avoid naming conflicts

# Example helper function
_vibe_template_helper() {
    log_debug "Helper function called"
}

# ── Before/After Hook Functions ───────────────────────────
# Define hook functions here

# Example before hook
# _vibe_template_before_some_command() {
#     log_debug "Before hook for some_command"
# }

# Example after hook
# _vibe_template_after_some_command() {
#     local exit_code="$1"
#     log_debug "After hook for some_command (exit: $exit_code)"
# }
