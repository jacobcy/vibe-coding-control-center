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
    vibe_tool_installed "claude" && tools+=("claude")
    vibe_tool_installed "opencode" && tools+=("opencode")
    vibe_tool_installed "codex" && tools+=("codex")
    echo "${tools[@]}"
}

# Save default tool selection
vibe_save_default_tool() {
    local tool="$1"
    local config_file="$VIBE_CONFIG[CONFIG_DIR]/config.local"
    local tmp_file

    if ! validate_input "$tool" "false"; then
        log_warn "Skipping save of invalid tool name: $tool"
        return 1
    fi

    tmp_file=$(mktemp) || return 1
    : > "$tmp_file"

    if [[ -f "$config_file" ]]; then
        grep -vE '^(export[[:space:]]+)?VIBE_DEFAULT_TOOL=' "$config_file" > "$tmp_file" 2>/dev/null || true
    fi

    printf '%s\n' "export VIBE_DEFAULT_TOOL=\"$tool\"" >> "$tmp_file"
    local content
    content=$(cat "$tmp_file")
    rm -f "$tmp_file"

    if secure_write_file "$config_file" "$content" "644"; then
        log_info "Default tool set to: $tool"
        return 0
    fi
    return 1
}

# Select default tool (prompt if needed)
vibe_select_default_tool() {
    local installed
    installed=($(vibe_list_installed_tools))

    if (( ${#installed[@]} == 0 )); then
        log_error "No supported tools found (claude/opencode/codex)"
        return 1
    fi

    if [[ -n "${VIBE_DEFAULT_TOOL:-}" ]] && vibe_tool_installed "$VIBE_DEFAULT_TOOL"; then
        echo "$VIBE_DEFAULT_TOOL"
        return 0
    fi

    echo -e "\n${BOLD}Select default tool:${NC}"
    local i=1
    for t in "${installed[@]}"; do
        echo "  $i) $t"
        i=$((i + 1))
    done

    local choice
    choice=$(prompt_user "Select tool (1-${#installed[@]})" "1" "")
    if [[ ! "$choice" =~ ^[0-9]+$ ]]; then
        log_warn "Invalid choice, defaulting to ${installed[1]}"
        echo "${installed[1]}"
        return 0
    fi
    local idx=$((choice - 1))
    if [[ $idx -lt 0 || $idx -ge ${#installed[@]} ]]; then
        log_warn "Invalid choice, defaulting to ${installed[1]}"
        echo "${installed[1]}"
        return 0
    fi

    local selected="${installed[$((idx + 1))]}"
    vibe_save_default_tool "$selected" || true
    echo "$selected"
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
