#!/usr/bin/env zsh
# core_commands.sh
# Core command functions for Vibe Coding Control Center

# Load dependencies
source "$VIBE_ROOT/lib/utils.sh" || source "$(dirname "${(%):-%x}")/utils.sh"
source "$VIBE_ROOT/lib/config.sh" || source "$(dirname "${(%):-%x}")/config.sh"
source "$VIBE_ROOT/lib/i18n.sh" || source "$(dirname "${(%):-%x}")/i18n.sh"
source "$VIBE_ROOT/lib/cache.sh" || source "$(dirname "${(%):-%x}")/cache.sh"
source "$VIBE_ROOT/lib/error_handling.sh" || source "$(dirname "${(%):-%x}")/error_handling.sh"
source "$VIBE_ROOT/lib/agents.sh" || source "$(dirname "${(%):-%x}")/agents.sh"

# ================= ACTIONS =================

# Check system status
check_status() {
    echo -e "\n${BOLD}SYSTEM STATUS:${NC}"

    # 1. OpenCode
    if command -v opencode &> /dev/null; then
        OPENCODE_VERSION=$(get_command_version "opencode" "--version")
        if [[ -n "$OPENCODE_VERSION" ]]; then
            log_info "OpenCode       : Installed (v$OPENCODE_VERSION)"
        else
            log_info "OpenCode       : Installed (version unknown)"
        fi
    else
        log_error "OpenCode       : Missing"
    fi

    # 2. Claude
    if command -v claude &> /dev/null; then
        CLAUDE_VERSION=$(get_command_version "claude" "--version")
        if [[ -n "$CLAUDE_VERSION" ]]; then
            log_info "Claude Code    : Installed (v$CLAUDE_VERSION)"
        else
            log_info "Claude Code    : Installed (version unknown)"
        fi
    else
        log_warn "Claude Code    : Missing (Optional)"
    fi

    # 3. oh-my-opencode
    if [ -f "$HOME/.oh-my-opencode/install.sh" ]; then
        log_info "oh-my-opencode : Installed"
    else
        log_warn "oh-my-opencode : Not installed"
    fi

    # 4. Environment
    KEYS_FILE="$HOME/.vibe/keys.env"
    if [ -f "$KEYS_FILE" ]; then
        log_info "Keys Config    : Found (~/.vibe/keys.env)"
    else
        log_warn "Keys Config    : Missing (~/.vibe/keys.env)"
    fi

    # 5. MCP Configuration
    if [ -f "$HOME/.claude.json" ]; then
        SERVER_COUNT=$(grep -o "\"command\"" "$HOME/.claude.json" 2>/dev/null | wc -l | tr -d ' ')
        log_info "MCP Config     : Found ($SERVER_COUNT servers)"
    else
        log_warn "MCP Config     : Missing (.claude.json)"
    fi

    echo -e "${BLUE}====================================${NC}"
}

# Project ignition function
do_ignition() {
    echo -e "\n${GREEN}>> INITIALIZING NEW PROJECT <<${NC}"

    vibe_collect_init_answers || return
    local mode="ai"
    vibe_init_project "$mode"

    echo -e "\n${GREEN}Ignition sequence complete.${NC}"
    press_enter "Press Enter to continue..."
}

# Initialize API keys
do_init_keys() {
    echo -e "\n${YELLOW}>> INITIALIZING API KEYS <<${NC}"
    
    local keys_template="${SCRIPT_DIR:-.}/../config/keys.template.env"
    local keys_file="$HOME/.vibe/keys.env"
    
    if [[ -f "$keys_file" ]]; then
        log_info "Keys file already exists: $keys_file"
        local confirm=$(prompt_user "Overwrite existing keys.env? (y/n)" "n")
        if [[ "$confirm" != "y" ]]; then
            return
        fi
    fi
    
    if [[ ! -f "$keys_template" ]]; then
        log_error "Template not found: $keys_template"
        press_enter "Press Enter to return..."
        return
    fi
    
    cp "$keys_template" "$keys_file"
    log_success "Initialized $keys_file from template."
    log_info "Please edit $keys_file with your actual API keys."
    
    # Try to open with editor if available
    local editor_cmd="${EDITOR:-vim}"
    if command -v "$editor_cmd" &> /dev/null; then
        local edit_now=$(prompt_user "Edit $keys_file now? (y/n)" "y")
        if [[ "$edit_now" == "y" ]]; then
            "$editor_cmd" "$keys_file"
            # Reload keys after editing
            load_user_config
        fi
    fi
    
    press_enter "Press Enter to continue..."
}

# Chat with AI tools
do_chat() {
    local tool
    tool=$(vibe_select_default_tool) || return 1

    case "$tool" in
        claude)
            claude
            ;;
        opencode)
            opencode
            ;;
        codex)
            codex
            ;;
        *)
            log_error "Unsupported tool: $tool"
            return 1
            ;;
    esac
}

# Sync workspace identity
do_sync_identity() {
    echo -e "\n${YELLOW}>> SYNCING WORKSPACE IDENTITY <<${NC}"
    
    # Check if we are in a git repo
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        log_error "Not inside a git repository or worktree."
        press_enter "Press Enter to return..."
        return
    fi
    
    # Identify agent type from directory name (wt-agent-branch)
    local dir_name=$(basename "$PWD")
    local agent="claude" # Default
    
    if [[ "$dir_name" =~ ^wt-([^-\ ]+)- ]]; then
        agent="${match[1]}"
    fi
    
    echo -e "Detected agent type: ${CYAN}$agent${NC}"
    local agent_choice=$(prompt_user "Confirm agent type (claude/opencode/codex)" "$agent")
    
    local agent_name="Agent-${agent_choice^}"
    local agent_email="agent-${agent_choice}@vibecoding.ai"
    
    git config user.name "$agent_name"
    git config user.email "$agent_email"
    
    log_success "Workspace identity synced."
    echo -e "  User Name  : $agent_name"
    echo -e "  User Email : $agent_email"
    
    press_enter "Press Enter to continue..."
}

# Equip tools function
do_equip() {
    echo -e "\n${YELLOW}>> EQUIPPING TOOLS (INSTALL/UPDATE) <<${NC}"

    # Show current versions
    if command -v opencode &> /dev/null; then
        OPENCODE_VER=$(get_command_version "opencode" "--version")
        if [[ -n "$OPENCODE_VER" ]]; then
            echo -e "1. Install/Update OpenCode ${CYAN}(current: v$OPENCODE_VER)${NC}"
        else
            echo "1. Install/Update OpenCode (installed)"
        fi
    else
        echo "1. Install/Update OpenCode (not installed)"
    fi

    if command -v claude &> /dev/null; then
        CLAUDE_VER=$(get_command_version "claude" "--version")
        if [[ -n "$CLAUDE_VER" ]]; then
            echo -e "2. Install/Update Claude Code ${CYAN}(current: v$CLAUDE_VER)${NC}"
        else
            echo "2. Install/Update Claude Code (installed)"
        fi
    else
        echo "2. Install/Update Claude Code (not installed)"
    fi

    echo "3. Back"

    # Use secure input validation
    CHOICE=$(prompt_user "Select option (1-3)" "" "")

    # Validate the selection
    case $CHOICE in
        1|2|3)
            # Valid choice, continue processing
            ;;
        *)
            log_error "Invalid option: $CHOICE"
            press_enter "Press Enter to continue..."
            return
            ;;
    esac

    case $CHOICE in
        1)
            zsh "${SCRIPT_DIR:-.}/../install/install-opencode.sh"
            ;;
        2)
            zsh "${SCRIPT_DIR:-.}/../install/install-claude.sh"
            ;;
        3)
            return
            ;;
    esac

    echo -e "\n${GREEN}Equipping complete. Please restart terminal if new env vars were added.${NC}"
    press_enter "Press Enter to continue..."
}

# Diagnostics function
do_diagnostics() {
    echo -e "\n${CYAN}>> RUNNING DIAGNOSTICS <<${NC}"
    echo "Checking core connections..."

    # Check MCP config
    if [ -f "$HOME/.claude.json" ]; then
        log_info "MCP Configuration found (.claude.json)"
        # Count servers using grep as a simple heuristic
        SERVER_COUNT=$(grep -o "\"command\"" "$HOME/.claude.json" | wc -l)
        echo -e "  - Configured Servers: $SERVER_COUNT"
    else
        log_error "MCP Configuration missing"
    fi

    # 6. Additional Dependencies
    echo -e "\n${BOLD}DEPENDENCIES:${NC}"
    for cmd in tmux lazygit zsh git; do
        if command -v "$cmd" &> /dev/null; then
            log_info "$(printf "%-14s" "$cmd") : Found"
        else
            log_error "$(printf "%-14s" "$cmd") : Missing"
        fi
    done

    # 7. Aliases Check
    echo -e "\n${BOLD}SHELL CONFIGURATION:${NC}"
    SHELL_RC="$HOME/.zshrc"
    if [ -f "$SHELL_RC" ]; then
        log_info ".zshrc found"
        local aliases=("c" "o" "x" "vibe" "vnew" "wt")
        for a in "${aliases[@]}"; do
            if grep -q "alias $a=" "$SHELL_RC"; then
                 log_info "Alias '$a' configured"
            else
                 log_warn "Alias '$a' likely missing"
            fi
        done
    else
        log_error ".zshrc not found"
    fi

    echo -e "\n${CYAN}Diagnostics complete.${NC}"
    press_enter "Press Enter to return..."
}

# Show main header
show_header() {
    clear
    echo -e "${PURPLE}"
    echo "   ______           __          "
    echo "  / ____/____  ____/ /__  _  __"
    echo " / /    / __ \/ __  / _ \| |/_/"
    echo "/ /___ / /_/ / /_/ /  __/>  <  "
    echo "\____/ \____/\__,_/\___/_/|_|  "
    echo -e "${NC}"
    echo -e "${CYAN}    VIBE CODING CONTROL CENTER${NC}"
    echo -e "${BLUE}====================================${NC}"
}