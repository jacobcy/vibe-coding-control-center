#!/usr/bin/env zsh
# agents.sh
# Tool selection and AI prompt execution

# Guard
if [[ -n "${VIBE_AGENTS_LOADED:-}" ]]; then
    return 0 2>/dev/null || exit 0
fi
readonly VIBE_AGENTS_LOADED=1

# Check if a tool is installed
vibe_tool_installed() {
    command -v "$1" >/dev/null 2>&1
}

# Return installed tools in priority order
vibe_list_installed_tools() {
    local tools=()
    vibe_tool_installed "opencode" && tools+=("opencode")
    vibe_tool_installed "claude" && tools+=("claude")
    vibe_tool_installed "codex" && tools+=("codex")
    echo "${tools[@]}"
}

# Save default tool selection
vibe_save_default_tool() {
    local tool="$1"

    if ! validate_input "$tool" "false"; then
        log_warn "Skipping save of invalid tool name: $tool"
        return 1
    fi

    # Use vibe config command to update keys.env
    "$VIBE_ROOT/bin/vibe-config" set VIBE_DEFAULT_TOOL "$tool"
}

# Select default tool (prompt if needed)
vibe_select_default_tool() {
    local installed
    installed=($(vibe_list_installed_tools))

    if (( ${#installed[@]} == 0 )); then
        log_error "No supported tools found (claude/opencode/codex)"
        return 1
    fi

    # Priority 1: Environment variable
    if [[ -n "${VIBE_DEFAULT_TOOL:-}" ]] && vibe_tool_installed "$VIBE_DEFAULT_TOOL"; then
        echo "$VIBE_DEFAULT_TOOL"
        return 0
    fi

    # Priority 2: keys.env configuration
    local config_default_tool=""
    local vibe_home="${VIBE_HOME:-$HOME/.vibe}"
    if [[ -f "$vibe_home/keys.env" ]]; then
        config_default_tool=$(grep "^VIBE_DEFAULT_TOOL=" "$vibe_home/keys.env" 2>/dev/null | cut -d= -f2- | sed 's/^"//;s/"$//' || echo "")
    fi
    
    if [[ -n "$config_default_tool" ]] && vibe_tool_installed "$config_default_tool"; then
        echo "$config_default_tool"
        return 0
    fi

    # Priority 3: Fallback to VIBE_AGENT identity if it matches an installed tool
    local config_agent=""
    if [[ -f "$vibe_home/keys.env" ]]; then
        config_agent=$(grep "^VIBE_AGENT=" "$vibe_home/keys.env" 2>/dev/null | cut -d= -f2- | sed 's/^"//;s/"$//' || echo "")
    fi
    if [[ -n "$config_agent" ]] && vibe_tool_installed "$config_agent"; then
        echo "$config_agent"
        return 0
    fi

    # Priority 4: Use first installed tool (opencode > claude > codex)
    echo "${installed[1]}"
}

# Run a single prompt with the selected tool
vibe_run_ai_prompt() {
    local tool="$1"
    local prompt="$2"

    case "$tool" in
        claude)
            claude -p "$prompt"
            ;;
        codex)
            codex exec "$prompt"
            ;;
        opencode)
            local model="${VIBE_OPENCODE_MODEL:-${OPENCODE_MODEL:-opencode/kimi-k2.5-free}}"
            opencode run "$prompt" -m "$model"
            ;;
        *)
            log_error "Unsupported tool: $tool"
            return 1
            ;;
    esac
}
