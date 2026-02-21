#!/usr/bin/env zsh
# lib/tool_manager.sh
# Tool management library for Vibe environment

# Resolve script directory for sourcing dependencies
_tool_manager_dir="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Source dependencies
if [[ -f "${_tool_manager_dir}/utils.sh" ]]; then
    source "${_tool_manager_dir}/utils.sh"
fi
if [[ -f "${_tool_manager_dir}/config.sh" ]]; then
    source "${_tool_manager_dir}/config.sh"
fi

# Tools directory location
VIBE_TOOLS_DIR="${VIBE_HOME:-$HOME/.vibe}/tools"

# Known tools configuration
typeset -gA VIBE_KNOWN_TOOLS
VIBE_KNOWN_TOOLS=(
    claude "Claude Code - Anthropic's AI coding assistant"
    opencode "OpenCode - Open source AI coding assistant"
    codex "Codex - OpenAI's coding model"
)

# List all available tools
# Usage: vibe_tool_list
vibe_tool_list() {
    echo "Available tools:"

    if [[ ! -d "$VIBE_TOOLS_DIR" ]]; then
        log_warn "Tools directory not found: $VIBE_TOOLS_DIR"
        echo ""
        log_info "Run 'vibe init' to create the directory structure"
        return 1
    fi

    local found=0

    # List known tools first
    for tool_name in ${(k)VIBE_KNOWN_TOOLS}; do
        local tool_desc="${VIBE_KNOWN_TOOLS[$tool_name]}"
        local tool_dir="$VIBE_TOOLS_DIR/$tool_name"
        local tool_status="not installed"
        local marker=""

        if [[ -d "$tool_dir" ]]; then
            if [[ -f "$tool_dir/enabled" ]]; then
                tool_status="enabled"
                marker=" ✓"
            else
                tool_status="disabled"
            fi
        fi

        echo "  $tool_name$marker"
        echo "    └─ $tool_status: $tool_desc"
        found=1
    done

    # List any other tool directories
    for tool_dir in "$VIBE_TOOLS_DIR"/*(N/); do
        local name=$(basename "$tool_dir")
        # Skip if already listed as known tool
        [[ -n "${VIBE_KNOWN_TOOLS[$name]:-}" ]] && continue

        local tool_status="disabled"
        local marker=""
        if [[ -f "$tool_dir/enabled" ]]; then
            tool_status="enabled"
            marker=" ✓"
        fi

        echo "  $name$marker ($tool_status)"
        found=1
    done

    if [[ $found -eq 0 ]]; then
        echo "  No tools configured"
        echo ""
        log_info "Install a tool with: vibe tool install <name>"
    fi
}

# Install a tool
# Usage: vibe_tool_install <tool_name>
vibe_tool_install() {
    local tool="$1"

    if [[ -z "$tool" ]]; then
        log_error "Tool name required"
        echo "Usage: vibe tool install <tool-name>"
        echo ""
        echo "Known tools: ${(k)VIBE_KNOWN_TOOLS}"
        return 1
    fi

    local tool_dir="$VIBE_TOOLS_DIR/$tool"

    if [[ -d "$tool_dir" ]]; then
        log_warn "Tool already installed: $tool"
        log_info "Use 'vibe tool enable $tool' to enable it"
        return 0
    fi

    # Create tool directory structure
    mkdir -p "$tool_dir"

    # Create default config
    cat > "$tool_dir/config.yaml" << EOF
# $tool configuration
name: $tool
enabled: false
installed: $(date +%Y-%m-%d)
EOF

    # Create MCP config placeholder
    touch "$tool_dir/mcp.yaml"

    log_success "Installed tool: $tool"
    log_info "Enable with: vibe tool enable $tool"

    # Run tool-specific installation if available
    case "$tool" in
        claude)
            _install_claude_specific
            ;;
        opencode)
            _install_opencode_specific
            ;;
    esac
}

# Internal: Claude-specific installation
_install_claude_specific() {
    local tool_dir="$VIBE_TOOLS_DIR/claude"

    # Add Claude-specific configuration
    cat > "$tool_dir/config.yaml" << EOF
# Claude Code configuration
name: claude
enabled: false
installed: $(date +%Y-%m-%d)

settings:
  model: claude-sonnet-4-5
  max_tokens: 4096
EOF

    log_info "Claude-specific configuration added"
}

# Internal: OpenCode-specific installation
_install_opencode_specific() {
    local tool_dir="$VIBE_TOOLS_DIR/opencode"

    cat > "$tool_dir/config.yaml" << EOF
# OpenCode configuration
name: opencode
enabled: false
installed: $(date +%Y-%m-%d)

settings:
  model: default
EOF

    log_info "OpenCode-specific configuration added"
}

# Uninstall a tool
# Usage: vibe_tool_uninstall <tool_name>
vibe_tool_uninstall() {
    local tool="$1"

    if [[ -z "$tool" ]]; then
        log_error "Tool name required"
        echo "Usage: vibe tool uninstall <tool-name>"
        return 1
    fi

    local tool_dir="$VIBE_TOOLS_DIR/$tool"

    if [[ ! -d "$tool_dir" ]]; then
        log_error "Tool not installed: $tool"
        return 1
    fi

    # Prevent uninstalling the default tool without confirmation
    local default_tool
    default_tool=$(vibe_yaml_get "tools_default" "claude" 2>/dev/null)
    if [[ "$tool" == "$default_tool" ]]; then
        log_warn "$tool is the default tool"
        log_info "Remove it from vibe.yaml defaults first if you want to uninstall"
        return 1
    fi

    rm -rf "$tool_dir"
    log_success "Uninstalled tool: $tool"
}

# Enable a tool
# Usage: vibe_tool_enable <tool_name>
vibe_tool_enable() {
    local tool="$1"

    if [[ -z "$tool" ]]; then
        log_error "Tool name required"
        echo "Usage: vibe tool enable <tool-name>"
        return 1
    fi

    local tool_dir="$VIBE_TOOLS_DIR/$tool"

    if [[ ! -d "$tool_dir" ]]; then
        log_error "Tool not installed: $tool"
        log_info "Install it first with: vibe tool install $tool"
        return 1
    fi

    touch "$tool_dir/enabled"
    log_success "Enabled tool: $tool"
}

# Disable a tool
# Usage: vibe_tool_disable <tool_name>
vibe_tool_disable() {
    local tool="$1"

    if [[ -z "$tool" ]]; then
        log_error "Tool name required"
        echo "Usage: vibe tool disable <tool-name>"
        return 1
    fi

    local tool_dir="$VIBE_TOOLS_DIR/$tool"

    if [[ ! -d "$tool_dir" ]]; then
        log_error "Tool not installed: $tool"
        return 1
    fi

    rm -f "$tool_dir/enabled"
    log_success "Disabled tool: $tool"
}

# Set default tool
# Usage: vibe_tool_default <tool_name>
vibe_tool_default() {
    local tool="$1"

    if [[ -z "$tool" ]]; then
        log_error "Tool name required"
        echo "Usage: vibe tool default <tool-name>"
        return 1
    fi

    local tool_dir="$VIBE_TOOLS_DIR/$tool"

    if [[ ! -d "$tool_dir" ]]; then
        log_error "Tool not installed: $tool"
        return 1
    fi

    # Update vibe.yaml
    local yaml_file="$VIBE_HOME/vibe.yaml"
    if [[ -f "$yaml_file" ]]; then
        # Update tools.default
        if grep -q "default:" "$yaml_file"; then
            sed -i '' "s/^\([[:space:]]*default:[[:space:]]*\).*/\1$tool/" "$yaml_file" 2>/dev/null || \
            sed -i "s/^\([[:space:]]*default:[[:space:]]*\).*/\1$tool/" "$yaml_file" 2>/dev/null
        fi
    fi

    log_success "Set default tool: $tool"
}

# Show tool status
# Usage: vibe_tool_status [tool_name]
vibe_tool_status() {
    local tool="${1:-}"

    if [[ -z "$tool" ]]; then
        # Show all tools status
        echo "Tool Status:"
        echo ""

        local default_tool
        default_tool=$(vibe_yaml_get "tools_default" "claude" 2>/dev/null)
        echo "  Default: $default_tool"
        echo ""

        vibe_tool_list
        return 0
    fi

    local tool_dir="$VIBE_TOOLS_DIR/$tool"

    if [[ ! -d "$tool_dir" ]]; then
        log_error "Tool not installed: $tool"
        return 1
    fi

    echo "Tool: $tool"
    echo "  Directory: $tool_dir"
    echo "  Enabled: $([[ -f "$tool_dir/enabled" ]] && echo "yes" || echo "no")"

    if [[ -f "$tool_dir/config.yaml" ]]; then
        echo "  Config: $tool_dir/config.yaml"
    fi

    if [[ -f "$tool_dir/mcp.yaml" ]]; then
        echo "  MCP: $tool_dir/mcp.yaml"
    fi
}
