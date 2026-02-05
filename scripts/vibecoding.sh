#!/bin/bash
# vibecoding.sh
# Vibe Coding Control Center (formerly Codex)
# Combines: Claude Code, OpenCode, and Project Initialization

set -e

# ================= LOAD UTILITIES =================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../lib/utils.sh"

# ================= COLORS =================
# Colors are defined in utils.sh
# Only define BOLD here as it's not in utils.sh
readonly BOLD='\033[1m'

# ================= HEADER =================
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

    # 1. Claude
    if command -v claude &> /dev/null; then
        CLAUDE_VERSION=$(get_command_version "claude" "--version")
        if [[ -n "$CLAUDE_VERSION" ]]; then
            log_info "Claude Code    : Installed (v$CLAUDE_VERSION)"
        else
            log_info "Claude Code    : Installed (version unknown)"
        fi
    else
        log_error "Claude Code    : Missing"
    fi

    # 2. OpenCode
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

    # 3. oh-my-opencode
    if [ -d "$HOME/.oh-my-opencode" ]; then
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

    # Use secure prompt with validation
    PROJ_NAME=$(prompt_user "Enter project name (create dir) or '.' for current" "." "validate_input")

    # Validate the project name for security
    if ! validate_input "$PROJ_NAME" "false"; then
        log_error "Invalid project name provided"
        read -p "Press Enter to return..."
        return
    fi

    # Sanitize the project name to prevent path traversal
    PROJ_NAME=$(sanitize_filename "$PROJ_NAME")

    # Validate path to prevent directory traversal
    if ! validate_path "$PROJ_NAME" "Project name validation failed"; then
        log_error "Invalid project path: $PROJ_NAME"
        read -p "Press Enter to return..."
        return
    fi

    # Fix for script path resolution
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    INIT_SCRIPT="$SCRIPT_DIR/../install/init-project.sh"

    if [ ! -f "$INIT_SCRIPT" ]; then
        log_critical "Error: init-project.sh not found at $INIT_SCRIPT"
        read -p "Press Enter to return..."
        return
    fi

    bash "$INIT_SCRIPT" "$PROJ_NAME"

    echo -e "\n${GREEN}Ignition sequence complete.${NC}"
    read -p "Press Enter to continue..."
}

do_equip() {
    echo -e "\n${YELLOW}>> EQUIPPING TOOLS (INSTALL/UPDATE) <<${NC}"

    # Show current versions
    if command -v claude &> /dev/null; then
        CLAUDE_VER=$(get_command_version "claude" "--version")
        if [[ -n "$CLAUDE_VER" ]]; then
            echo -e "1. Install/Update Claude Code ${CYAN}(current: v$CLAUDE_VER)${NC}"
        else
            echo "1. Install/Update Claude Code (installed)"
        fi
    else
        echo "1. Install/Update Claude Code (not installed)"
    fi

    if command -v opencode &> /dev/null; then
        OPENCODE_VER=$(get_command_version "opencode" "--version")
        if [[ -n "$OPENCODE_VER" ]]; then
            echo -e "2. Install/Update OpenCode ${CYAN}(current: v$OPENCODE_VER)${NC}"
        else
            echo "2. Install/Update OpenCode (installed)"
        fi
    else
        echo "2. Install/Update OpenCode (not installed)"
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
            read -p "Press Enter to continue..."
            return
            ;;
    esac

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    case $CHOICE in
        1)
            bash "$SCRIPT_DIR/../install/install-claude.sh"
            ;;
        2)
            bash "$SCRIPT_DIR/../install/install-opencode.sh"
            ;;
        3)
            return
            ;;
    esac

    echo -e "\n${GREEN}Equipping complete. Please restart terminal if new env vars were added.${NC}"
    read -p "Press Enter to continue..."
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

    # Check Aliases
    # Note: Aliases are hard to check in script because they are not expanded in non-interactive shell usually.
    # We check the RC file instead.
    SHELL_RC="$HOME/.zshrc"
    if [ -f "$SHELL_RC" ]; then
        if grep -q "alias c=" "$SHELL_RC"; then
             log_info "Alias 'c' configured in .zshrc"
        else
             log_warn "Alias 'c' likely missing from .zshrc"
        fi

        if grep -q "alias o=" "$SHELL_RC"; then
             log_info "Alias 'o' configured in .zshrc"
        else
             log_warn "Alias 'o' likely missing from .zshrc"
        fi
    fi

    echo -e "\n${CYAN}Diagnostics complete.${NC}"
    read -p "Press Enter to return..."
}

# ================= MAIN LOOP =================
while true; do
    show_header
    check_status

    echo -e "${BOLD}COMMANDS:${NC}"
    echo -e "  ${GREEN}1)${NC} ${BOLD}IGNITION${NC}    (Start New Project)"
    echo -e "  ${GREEN}2)${NC} ${BOLD}EQUIP${NC}       (Install/Update Tools)"
    echo -e "  ${GREEN}3)${NC} ${BOLD}DIAGNOSTICS${NC} (System Check)"
    echo -e "  ${RED}q)${NC} Quit"
    echo ""

    # Use secure input validation
    OPTION=$(prompt_user "Select command (1-3, q)" "" "")

    case $OPTION in
        1) do_ignition ;;
        2) do_equip ;;
        3) do_diagnostics ;;
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
