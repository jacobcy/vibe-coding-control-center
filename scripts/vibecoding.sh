#!/usr/bin/env zsh
# vibecoding.sh
# Vibe Coding Control Center (formerly Codex)
# Combines: Claude Code, OpenCode, and Project Initialization

if [ -z "${ZSH_VERSION:-}" ]; then
    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi

    echo "zsh not found. Attempting to install..." >&2
    SUDO=""
    if [ "$(id -u)" -ne 0 ]; then
        if command -v sudo >/dev/null 2>&1; then
            SUDO="sudo"
        else
            echo "sudo not available; please install zsh manually." >&2
            exit 1
        fi
    fi

    if command -v brew >/dev/null 2>&1; then
        brew install zsh
    elif command -v apt-get >/dev/null 2>&1; then
        $SUDO apt-get update && $SUDO apt-get install -y zsh
    elif command -v dnf >/dev/null 2>&1; then
        $SUDO dnf install -y zsh
    elif command -v yum >/dev/null 2>&1; then
        $SUDO yum install -y zsh
    elif command -v pacman >/dev/null 2>&1; then
        $SUDO pacman -Sy --noconfirm zsh
    elif command -v apk >/dev/null 2>&1; then
        $SUDO apk add zsh
    else
        echo "No supported package manager found to install zsh." >&2
        exit 1
    fi

    if command -v zsh >/dev/null 2>&1; then
        exec zsh -l "$0" "$@"
    fi

    echo "zsh install failed; please install zsh and re-run." >&2
    exit 1
fi

set -e

# Ensure core utilities are on PATH (non-login shells may have a minimal PATH)
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# ================= LOAD UTILITIES =================
SCRIPT_DIR="$(cd "$(dirname "${(%):-%x}")" && pwd)"

# Load all utility modules
source "$SCRIPT_DIR/../lib/utils.sh"
source "$SCRIPT_DIR/../lib/config.sh"
source "$SCRIPT_DIR/../lib/i18n.sh"
source "$SCRIPT_DIR/../lib/cache.sh"
source "$SCRIPT_DIR/../lib/error_handling.sh"
source "$SCRIPT_DIR/../lib/agents.sh"
source "$SCRIPT_DIR/../lib/init_project.sh"

# Load config metadata (no env export)
load_user_config

# Re-ensure PATH after loading user config
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

ensure_oh_my_zsh || true
# ================= COLORS =================
# Colors are defined in utils.sh
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

# ================= STATUS CHECK =================
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
    KEYS_FILE="$SCRIPT_DIR/../config/keys.env"
    if [ -f "$KEYS_FILE" ]; then
        log_info "Keys Config    : Found (keys.env)"
    else
        log_warn "Keys Config    : Missing (config/keys.env)"
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

# ================= ACTIONS =================

do_ignition() {
    echo -e "\n${GREEN}>> INITIALIZING NEW PROJECT <<${NC}"

    vibe_collect_init_answers || return
    local mode="ai"
    vibe_init_project "$mode"

    echo -e "\n${GREEN}Ignition sequence complete.${NC}"
    press_enter "Press Enter to continue..."
}

do_init_keys() {
    echo -e "\n${YELLOW}>> INITIALIZING API KEYS <<${NC}"
    
    local keys_template="$SCRIPT_DIR/../config/keys.template.env"
    local keys_file="$SCRIPT_DIR/../config/keys.env"
    
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
            zsh "$SCRIPT_DIR/../install/install-opencode.sh"
            ;;
        2)
            zsh "$SCRIPT_DIR/../install/install-claude.sh"
            ;;
        3)
            return
            ;;
    esac

    echo -e "\n${GREEN}Equipping complete. Please restart terminal if new env vars were added.${NC}"
    press_enter "Press Enter to continue..."
}

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

# ================= CLI COMMAND HANDLING =================
if [[ $# -gt 0 ]]; then
    COMMAND="$1"
    shift
    
    case "$COMMAND" in
        tdd)
            if [[ "$1" == "new" ]]; then
                shift
                zsh "$SCRIPT_DIR/../scripts/tdd-init.sh" "$@"
                exit 0
            else
                log_error "Usage: vibe tdd new <feature-name>"
                exit 1
            fi
            ;;
        sync)
            do_sync_identity
            exit 0
            ;;
        keys)
            zsh "$SCRIPT_DIR/env-manager.sh" keys "$@"
            exit 0
            ;;
        env)
            zsh "$SCRIPT_DIR/env-manager.sh" "$@"
            exit 0
            ;;
        chat)
            do_chat
            exit 0
            ;;
        equip)
            do_equip
            exit 0
            ;;
        diagnostics)
            do_diagnostics
            exit 0
            ;;
        init)
            local mode="ai"
            if [[ "$1" == "--local" ]]; then
                mode="local"
                shift
            elif [[ "$1" == "--ai" ]]; then
                mode="ai"
                shift
            fi
            local preset_dir="${1:-}"
            vibe_collect_init_answers "$preset_dir" || exit 1
            vibe_init_project "$mode" || exit 1
            exit 0
            ;;
        *)
            # If command unknown, default to showing the menu but warn
            log_warn "Unknown command: $COMMAND. Entering interactive mode..."
            sleep 1
            ;;
    esac
fi

# ================= MAIN LOOP =================
while true; do
    show_header
    check_status

    echo -e "${BOLD}COMMANDS:${NC}"
    echo -e "  ${GREEN}1)${NC} ${BOLD}IGNITION${NC}    (Start New Project)"
    echo -e "  ${GREEN}2)${NC} ${BOLD}EQUIP${NC}       (Install/Update Tools)"
    echo -e "  ${GREEN}3)${NC} ${BOLD}ENV${NC}         (Environment & Keys)"
    echo -e "  ${GREEN}4)${NC} ${BOLD}SYNC${NC}        (Sync Workspace Identity)"
    echo -e "  ${GREEN}5)${NC} ${BOLD}DIAGNOSTICS${NC} (System Check)"
    echo -e "  ${RED}q)${NC} Quit"
    echo ""

    OPTION=$(prompt_user "Select command (1-5, q)" "" "")

    case $OPTION in
        1) do_ignition ;;
        2) do_equip ;;
        3) zsh "$SCRIPT_DIR/env-manager.sh" ;;
        4) do_sync_identity ;;
        5) do_diagnostics ;;
        q|Q)
            log_success "Happy Coding!"
            exit 0
            ;;
        *)
            log_warn "Invalid option: $OPTION"
            sleep 1
            ;;
    esac
done
