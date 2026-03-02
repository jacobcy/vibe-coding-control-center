#!/usr/bin/env zsh
# v3/lib/core/router.sh - Command Router
# Routes CLI commands to capability modules

# ── Router State ──────────────────────────────────────────
typeset -A _VIBE_CAPABILITY_MAP
typeset -a _VIBE_CAPABILITY_ORDER

# ── Capability Discovery ──────────────────────────────────
# Discovers all available capabilities from lib/capabilities/
vibe_discover_capabilities() {
    local cap_dir="$VIBE_ROOT/lib/capabilities"

    # Clear existing mappings
    _VIBE_CAPABILITY_MAP=()
    _VIBE_CAPABILITY_ORDER=()

    # Scan for capability modules
    if [[ -d "$cap_dir" ]]; then
        for cap_file in "$cap_dir"/*.sh(N); do
            local cap_name="${cap_file:t:r}"
            _VIBE_CAPABILITY_MAP[$cap_name]="$cap_file"
            _VIBE_CAPABILITY_ORDER+="$cap_name"
        done
    fi

    # Sort capabilities alphabetically for deterministic order
    _VIBE_CAPABILITY_ORDER=(${(o)_VIBE_CAPABILITY_ORDER})
}

# ── Capability Registration ───────────────────────────────
# Registers a capability module
# Usage: vibe_register_capability <name> <file>
vibe_register_capability() {
    local name="$1"
    local file="$2"

    if [[ -z "$name" || -z "$file" ]]; then
        log_error "Usage: vibe_register_capability <name> <file>"
        return 1
    fi

    if [[ ! -f "$file" ]]; then
        log_error "Capability file not found: $file"
        return 1
    fi

    _VIBE_CAPABILITY_MAP[$name]="$file"
}

# ── Command Routing ───────────────────────────────────────
# Routes command to appropriate capability
# Usage: vibe_route_command <command> [args...]
vibe_route_command() {
    local command="${1:-help}"
    shift 2>/dev/null || true

    # Discover capabilities on first call
    if [[ ${#_VIBE_CAPABILITY_MAP[@]} -eq 0 ]]; then
        vibe_discover_capabilities
    fi

    # Built-in commands (not capabilities)
    case "$command" in
        help|--help|-h)
            vibe_show_help
            return 0
            ;;
        version|-v|--version)
            echo "Vibe $VIBE_VERSION"
            return 0
            ;;
        alias)
            source "$VIBE_CONFIG/aliases.sh"
            log_success "Aliases loaded"
            return 0
            ;;
    esac

    # Route to capability
    if [[ -n "${_VIBE_CAPABILITY_MAP[$command]:-}" ]]; then
        local cap_file="${_VIBE_CAPABILITY_MAP[$command]}"

        # Source the capability module
        source "$cap_file"

        # Call the capability's main function (vibe_<command>)
        local func_name="vibe_${command}"
        if typeset -f "$func_name" > /dev/null; then
            "$func_name" "$@"
        else
            log_error "Capability '$command' loaded but function '$func_name' not found"
            return 1
        fi
    else
        # Unknown command
        echo "${BOLD}Vibe Coding Control Center${NC} v${VIBE_VERSION}"
        echo ""
        echo "Usage: ${CYAN}vibe <command>${NC} [args]"
        echo "Unknown command: $command"
        echo ""
        echo "Available commands: ${(j:, :)_VIBE_CAPABILITY_ORDER}"
        return 1
    fi
}

# ── Help System ───────────────────────────────────────────
vibe_show_help() {
    echo "${BOLD}Vibe Coding Control Center${NC} v${VIBE_VERSION}"
    echo ""
    echo "Usage: ${CYAN}vibe <command>${NC} [args]"
    echo ""
    echo "Commands:"

    # Discover capabilities if not already done
    if [[ ${#_VIBE_CAPABILITY_MAP[@]} -eq 0 ]]; then
        vibe_discover_capabilities
    fi

    # List available capabilities
    for cap_name in "${_VIBE_CAPABILITY_ORDER[@]}"; do
        echo "  ${GREEN}${cap_name}${NC}"
    done

    echo ""
    echo "Built-in commands:"
    echo "  ${GREEN}help${NC}     显示此帮助信息"
    echo "  ${GREEN}version${NC}  显示版本号"
    echo "  ${GREEN}alias${NC}    加载 shell 快捷别名"
}

# ── Capability List ───────────────────────────────────────
# Returns list of available capabilities
# Usage: vibe_list_capabilities
vibe_list_capabilities() {
    if [[ ${#_VIBE_CAPABILITY_MAP[@]} -eq 0 ]]; then
        vibe_discover_capabilities
    fi

    echo "${(j:\n:)_VIBE_CAPABILITY_ORDER}"
}
